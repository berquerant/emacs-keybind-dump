"""CLI entry point for keybind-dump."""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import signal
import sys
from typing import Any

from keybind_dump.dumper import iter_dump
from keybind_dump.models import KeybindCollection
from keybind_dump.stats import (
    keymap_duplicate_stats,
    overall_summary_stats,
    sequence_duplicate_stats,
)


def _load_collection(
    file_path: str | None,
    dump: bool = False,
    init_dir: str | None = None,
    init_file: str | None = None,
    quick: bool = False,
    emacs_bin: str | None = None,
    verbose: bool = False,
) -> KeybindCollection:
    """Load KeybindCollection from a file, standard input, or direct Emacs execution.

    Loading priority:
    1. If `dump=True` or (`file_path` is None and standard input is a terminal TTY),
       launches Emacs in batch mode to dump keybindings dynamically.
    2. If `file_path` is specified and not '-', reads from the designated JSONL file.
    3. If `file_path` is '-' or omitted while standard input is piped/redirected,
       reads JSON Lines from `sys.stdin`.
    4. Otherwise, falls back to direct Emacs execution.
    """
    # 1. If explicit dump requested or (input is not specified and stdin is interactive)
    should_dump = dump or (file_path is None and sys.stdin.isatty())

    if should_dump:
        lines = iter_dump(
            init_dir=init_dir,
            init_file=init_file,
            quick=quick,
            emacs_bin=emacs_bin,
            verbose=verbose,
        )
        return KeybindCollection.from_jsonl(lines)

    # 2. From file or stdin
    if file_path and file_path != "-":
        with open(file_path, "r", encoding="utf-8") as f:
            return KeybindCollection.from_jsonl(f)
    else:
        if sys.stdin.isatty():
            # Fallback to direct dump if stdin is terminal
            lines = iter_dump(
                init_dir=init_dir,
                init_file=init_file,
                quick=quick,
                emacs_bin=emacs_bin,
                verbose=verbose,
            )
            return KeybindCollection.from_jsonl(lines)
        return KeybindCollection.from_jsonl(sys.stdin)


def _format_stats(
    collection: KeybindCollection,
    target: str,
    fmt: str,
    min_count: int,
    limit: int | None,
) -> str:
    """Format duplicate statistics as text, json, or tsv.

    Arguments:
        collection: The keybinding collection to calculate metrics from.
        target: Target metrics domain ('sequence', 'keymap', or 'both').
        fmt: Output format representation ('text', 'json', or 'tsv').
        min_count: Minimum occurrence threshold for sequence duplication reporting.
        limit: Maximum number of rows/items to report.
    """
    summary = overall_summary_stats(collection)

    seq_stats = []
    if target in ("sequence", "both"):
        seq_stats = sequence_duplicate_stats(collection, min_count=min_count)
        if limit:
            seq_stats = seq_stats[:limit]

    km_stats = []
    if target in ("keymap", "both"):
        km_stats = keymap_duplicate_stats(collection)
        if limit:
            km_stats = km_stats[:limit]

    if fmt == "json":
        data: dict[str, Any] = {
            "summary": {
                "total_records": summary.total_records,
                "unique_sequences": summary.unique_sequences,
                "unique_keymaps": summary.unique_keymaps,
                "shared_sequences": summary.shared_sequences,
                "sequence_conflict_rate": round(summary.sequence_conflict_rate, 4),
            }
        }
        if target in ("sequence", "both"):
            data["sequences"] = [
                {
                    "sequence": s.sequence,
                    "count": s.count,
                    "keymaps": s.keymaps,
                    "distinct_commands_count": s.distinct_commands_count,
                    "has_conflict": s.has_conflict,
                    "commands": s.commands,
                }
                for s in seq_stats
            ]
        if target in ("keymap", "both"):
            data["keymaps"] = [
                {
                    "keymap": k.keymap,
                    "total_bindings": k.total_bindings,
                    "exclusive_bindings": k.exclusive_bindings,
                    "shared_bindings": k.shared_bindings,
                    "conflict_rate": round(k.conflict_rate, 4),
                    "total_duplicate_score": k.total_duplicate_score,
                    "top_overlaps": [
                        {"keymap": other_km, "shared_count": cnt}
                        for other_km, cnt in k.top_overlaps
                    ],
                }
                for k in km_stats
            ]
        return json.dumps(data, separators=(",", ":"), ensure_ascii=False) + "\n"

    elif fmt == "tsv":
        out = io.StringIO()
        writer = csv.writer(out, delimiter="\t", lineterminator="\n")
        if target == "sequence":
            writer.writerow(["sequence", "count", "has_conflict", "keymaps", "commands"])
            for s in seq_stats:
                cmd_repr = "; ".join(f"{km}->{cmd}" for km, cmd in sorted(s.commands.items()))
                writer.writerow([s.sequence, s.count, str(s.has_conflict), ",".join(s.keymaps), cmd_repr])
        elif target == "keymap":
            writer.writerow([
                "keymap",
                "total_bindings",
                "exclusive_bindings",
                "shared_bindings",
                "conflict_rate",
                "total_duplicate_score",
                "top_overlaps",
            ])
            for k in km_stats:
                ov_repr = "; ".join(f"{other}:{cnt}" for other, cnt in k.top_overlaps)
                writer.writerow([
                    k.keymap,
                    k.total_bindings,
                    k.exclusive_bindings,
                    k.shared_bindings,
                    f"{k.conflict_rate:.1%}",
                    k.total_duplicate_score,
                    ov_repr,
                ])
        else:
            # both
            writer.writerow(["# Overall Summary"])
            writer.writerow(["total_records", "unique_sequences", "unique_keymaps", "shared_sequences", "conflict_rate"])
            writer.writerow([
                summary.total_records,
                summary.unique_sequences,
                summary.unique_keymaps,
                summary.shared_sequences,
                f"{summary.sequence_conflict_rate:.1%}",
            ])
            writer.writerow([])
            writer.writerow(["# Sequence Duplicate Stats"])
            writer.writerow(["sequence", "count", "has_conflict", "keymaps", "commands"])
            for s in seq_stats:
                cmd_repr = "; ".join(f"{km}->{cmd}" for km, cmd in sorted(s.commands.items()))
                writer.writerow([s.sequence, s.count, str(s.has_conflict), ",".join(s.keymaps), cmd_repr])
            writer.writerow([])
            writer.writerow(["# Keymap Duplicate Stats"])
            writer.writerow([
                "keymap",
                "total_bindings",
                "exclusive_bindings",
                "shared_bindings",
                "conflict_rate",
                "total_duplicate_score",
                "top_overlaps",
            ])
            for k in km_stats:
                ov_repr = "; ".join(f"{other}:{cnt}" for other, cnt in k.top_overlaps)
                writer.writerow([
                    k.keymap,
                    k.total_bindings,
                    k.exclusive_bindings,
                    k.shared_bindings,
                    f"{k.conflict_rate:.1%}",
                    k.total_duplicate_score,
                    ov_repr,
                ])
        return out.getvalue()

    else:
        # text format
        lines = []
        if target == "both":
            lines.append("=== Summary Overview ===")
            lines.append(
                f"Records: {summary.total_records} | Sequences: {summary.unique_sequences} | "
                f"Keymaps: {summary.unique_keymaps} | Shared Sequences: {summary.shared_sequences} ({summary.sequence_conflict_rate:.1%})"
            )
            lines.append("")

        if target in ("sequence", "both"):
            lines.append("=== Sequence Duplicate Stats ===")
            for s in seq_stats:
                status = "conflict" if s.has_conflict else "same-cmd"
                cmd_summary = ", ".join(f"{km}->{cmd}" for km, cmd in sorted(s.commands.items()))
                lines.append(f"[{s.sequence}] in {s.count} maps ({status}): {cmd_summary}")

        if target in ("keymap", "both"):
            if lines and target != "both" or lines and target == "both":
                lines.append("")
            lines.append("=== Keymap Duplicate Stats ===")
            for k in km_stats:
                ov_str = ", ".join(f"{other} ({cnt})" for other, cnt in k.top_overlaps) if k.top_overlaps else "none"
                lines.append(
                    f"{k.keymap}:\n"
                    f"  total: {k.total_bindings:d}, exclusive: {k.exclusive_bindings:d}, shared: {k.shared_bindings:d} ({k.conflict_rate:.1%}) | score: {k.total_duplicate_score}\n"
                    f"  top overlaps: {ov_str}"
                )
        return "\n".join(lines) + ("\n" if lines else "")


def _format_collection(
    collection: KeybindCollection,
    fmt: str,
    target_keymaps: list[str] | None,
    none_value: str,
    duplicates_only: bool,
    limit: int | None,
) -> str:
    """Format keybinding collection as text, tsv, json, or jsonl.

    Arguments:
        collection: The filtered keybinding collection to output.
        fmt: Target serialization format ('text', 'tsv', 'json', or 'jsonl').
        target_keymaps: Specific keymaps to extract as columns in TSV matrix mode.
        none_value: Placeholder value for missing keybindings in TSV matrix.
        duplicates_only: Filter flag indicating only sequences with >=2 keymaps.
        limit: Maximum number of rows/lines to output.
    """
    if fmt == "tsv":
        return collection.to_tsv(
            target_keymaps=target_keymaps,
            none_value=none_value,
            duplicates_only=duplicates_only,
        )

    nested = collection.to_nested_dict()

    if fmt == "json":
        if limit is not None:
            nested = {seq: nested[seq] for seq in sorted(nested.keys())[:limit]}
        return json.dumps(nested, separators=(",", ":"), ensure_ascii=False) + "\n"

    elif fmt == "jsonl":
        out = io.StringIO()
        count = 0
        for seq, km_map in sorted(nested.items()):
            for km, cmd in sorted(km_map.items()):
                out.write(json.dumps({"sequence": seq, "keymap": km, "command": cmd}, separators=(",", ":"), ensure_ascii=False) + "\n")
                count += 1
                if limit and count >= limit:
                    return out.getvalue()
        return out.getvalue()

    else:
        # text format
        lines = []
        for seq, km_map in sorted(nested.items()):
            for km, cmd in sorted(km_map.items()):
                lines.append(f"[{seq}] {km} -> {cmd}")
                if limit and len(lines) >= limit:
                    break
            if limit and len(lines) >= limit:
                break
        return "\n".join(lines) + ("\n" if lines else "")


def main() -> None:
    # Handle broken pipe smoothly when stdout is closed early (e.g. piped to head)
    if hasattr(signal, "SIGPIPE"):
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)

    default_init_dir = os.environ.get("EMACSD") or os.environ.get("EMACS_INIT_DIR")

    parser = argparse.ArgumentParser(
        prog="keybind-dump",
        description="Dump, filter, analyze, and format Emacs keybindings",
    )
    parser.add_argument(
        "input",
        nargs="?",
        default=None,
        help="Input JSONL file or - for stdin (if omitted and not piped, dumps directly from Emacs)",
    )

    # Dump source options
    g_dump = parser.add_argument_group("Dump options (when running directly with Emacs)")
    g_dump.add_argument(
        "--dump",
        action="store_true",
        help="Force dumping keybindings directly from Emacs",
    )
    g_dump.add_argument(
        "-d",
        "--init-directory",
        default=default_init_dir,
        help="Emacs init directory and load DIR/init.el (default: $EMACSD or $EMACS_INIT_DIR)",
    )
    g_dump.add_argument(
        "-i",
        "--init-file",
        default=os.environ.get("EMACS_INIT_FILE"),
        help="Emacs init file to load (default: $EMACS_INIT_FILE)",
    )
    g_dump.add_argument(
        "-Q",
        "--quick",
        action="store_true",
        help="Run without loading user init (default when neither init-directory nor init-file is specified)",
    )
    g_dump.add_argument(
        "--emacs-bin",
        default=os.environ.get("EMACS_BIN", "emacs"),
        help="Path to emacs executable (default: $EMACS_BIN or emacs)",
    )
    g_dump.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show Emacs stderr even when execution succeeds",
    )

    # Filter options
    g_filter = parser.add_argument_group("Filter options")
    g_filter.add_argument("-D", "--duplicates-only", action="store_true", help="Include only sequences with >=2 keymaps")
    g_filter.add_argument("-s", "--sequence", dest="seq_pattern", help="Filter by sequence regex pattern")
    g_filter.add_argument("-k", "--keymap", action="append", dest="keymap_patterns", help="Filter by keymap regex pattern (can be specified multiple times; also defines TSV columns)")
    g_filter.add_argument("-c", "--command", dest="cmd_pattern", help="Filter by command regex pattern")

    # Stats mode option
    g_stats = parser.add_argument_group("Summary / Statistics options")
    g_stats.add_argument(
        "--stats",
        nargs="?",
        const="both",
        choices=["sequence", "keymap", "both"],
        help="Calculate duplicate statistics summary (default target: both)",
    )
    g_stats.add_argument("--min-count", type=int, default=2, help="Min duplicate count for sequence stats (default: 2)")
    g_stats.add_argument("--limit", type=int, help="Max entries to output")

    # Output formatting options
    g_fmt = parser.add_argument_group("Output formatting options")
    g_fmt.add_argument(
        "-f",
        "--format",
        choices=["text", "tsv", "json", "jsonl"],
        default="text",
        help="Output format (default: text)",
    )
    g_fmt.add_argument("--none-value", default="None", help="Placeholder for missing bindings in TSV matrix (default: None)")
    g_fmt.add_argument("-o", "--output", help="Write output to file instead of stdout")

    args = parser.parse_args()

    collection = _load_collection(
        file_path=args.input,
        dump=args.dump,
        init_dir=args.init_directory,
        init_file=args.init_file,
        quick=args.quick,
        emacs_bin=args.emacs_bin,
        verbose=args.verbose,
    )

    # Combine keymap patterns if multiple specified (e.g. "^(km1|km2)$")
    km_pattern = None
    if args.keymap_patterns:
        km_pattern = f"^({'|'.join(args.keymap_patterns)})$" if len(args.keymap_patterns) > 1 else args.keymap_patterns[0]

    filtered = collection.filter(
        sequence_pattern=args.seq_pattern,
        keymap_pattern=km_pattern,
        command_pattern=args.cmd_pattern,
        duplicates_only=args.duplicates_only,
    )

    if args.stats:
        output_str = _format_stats(
            filtered,
            target=args.stats,
            fmt=args.format,
            min_count=args.min_count,
            limit=args.limit,
        )
    else:
        output_str = _format_collection(
            filtered,
            fmt=args.format,
            target_keymaps=args.keymap_patterns,
            none_value=args.none_value,
            duplicates_only=args.duplicates_only,
            limit=args.limit,
        )

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output_str)
    else:
        sys.stdout.write(output_str)


if __name__ == "__main__":
    main()
