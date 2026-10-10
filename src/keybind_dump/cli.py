"""CLI entry point for keybind-dump."""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import signal
import sys
from typing import List, Optional

from keybind_dump.dumper import run_dump
from keybind_dump.models import KeyBinding, KeybindCollection
from keybind_dump.stats import (
    keymap_duplicate_stats,
    sequence_duplicate_stats,
)


def _load_collection(file_path: Optional[str]) -> KeybindCollection:
    if file_path and file_path != "-":
        with open(file_path, "r", encoding="utf-8") as f:
            return KeybindCollection.from_jsonl(f)
    else:
        if sys.stdin.isatty():
            print(
                "Error: No input file specified and stdin is an interactive terminal.\n"
                "Please provide a JSONL file or pipe data via stdin. (Run with -h for help)",
                file=sys.stderr,
            )
            sys.exit(1)
        return KeybindCollection.from_jsonl(sys.stdin)


def _format_stats(
    collection: KeybindCollection,
    target: str,
    fmt: str,
    min_count: int,
    limit: Optional[int],
) -> str:
    """Format duplicate statistics as text, json, or tsv."""
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
        data = {}
        if target in ("sequence", "both"):
            data["sequences"] = [
                {"sequence": s.sequence, "count": s.count, "keymaps": s.keymaps}
                for s in seq_stats
            ]
        if target in ("keymap", "both"):
            data["keymaps"] = [
                {
                    "keymap": k.keymap,
                    "total_duplicate_score": k.total_duplicate_score,
                    "unique_bindings_count": k.unique_bindings_count,
                }
                for k in km_stats
            ]
        return json.dumps(data, indent=2, ensure_ascii=False) + "\n"

    elif fmt == "tsv":
        out = io.StringIO()
        writer = csv.writer(out, delimiter="\t", lineterminator="\n")
        if target == "sequence":
            writer.writerow(["sequence", "count", "keymaps"])
            for s in seq_stats:
                writer.writerow([s.sequence, s.count, ",".join(s.keymaps)])
        elif target == "keymap":
            writer.writerow(["keymap", "total_duplicate_score", "unique_bindings_count"])
            for k in km_stats:
                writer.writerow([k.keymap, k.total_duplicate_score, k.unique_bindings_count])
        else:
            # both
            writer.writerow(["# Sequence Duplicate Stats"])
            writer.writerow(["sequence", "count", "keymaps"])
            for s in seq_stats:
                writer.writerow([s.sequence, s.count, ",".join(s.keymaps)])
            writer.writerow([])
            writer.writerow(["# Keymap Duplicate Stats"])
            writer.writerow(["keymap", "total_duplicate_score", "unique_bindings_count"])
            for k in km_stats:
                writer.writerow([k.keymap, k.total_duplicate_score, k.unique_bindings_count])
        return out.getvalue()

    else:
        # text format
        lines = []
        if target in ("sequence", "both"):
            lines.append("=== Sequence Duplicate Stats ===")
            for s in seq_stats:
                lines.append(f"{s.count:3d} keymaps: '{s.sequence}' (maps: {', '.join(s.keymaps)})")
        if target in ("keymap", "both"):
            if lines:
                lines.append("")
            lines.append("=== Keymap Total Duplicate Score Stats ===")
            for k in km_stats:
                lines.append(
                    f"score: {k.total_duplicate_score:4d} (total bindings: {k.unique_bindings_count:4d}) - {k.keymap}"
                )
        return "\n".join(lines) + ("\n" if lines else "")


def _format_collection(
    collection: KeybindCollection,
    fmt: str,
    target_keymaps: Optional[list[str]],
    none_value: str,
    duplicates_only: bool,
    limit: Optional[int],
) -> str:
    """Format keybinding collection as text, tsv, json, or jsonl."""
    if fmt == "tsv":
        return collection.to_tsv(
            target_keymaps=target_keymaps,
            none_value=none_value,
            duplicates_only=duplicates_only,
        )

    nested = collection.to_nested_dict()

    if fmt == "json":
        return json.dumps(nested, indent=2, ensure_ascii=False) + "\n"

    elif fmt == "jsonl":
        out = io.StringIO()
        count = 0
        for seq, km_map in sorted(nested.items()):
            for km, cmd in sorted(km_map.items()):
                out.write(json.dumps({"sequence": seq, "keymap": km, "command": cmd}, ensure_ascii=False) + "\n")
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

    parser = argparse.ArgumentParser(
        prog="keybind-dump",
        description="Filter, analyze, format, and dump Emacs keybindings",
    )
    subparsers = parser.add_subparsers(dest="subcommand")

    # dump subcommand
    p_dump = subparsers.add_parser(
        "dump",
        help="Dump keybindings from Emacs to JSONL",
        description="Run Emacs in batch mode to dump keybindings as JSON Lines.",
    )
    default_init_dir = os.environ.get("EMACSD") or os.environ.get("EMACS_INIT_DIR")
    p_dump.add_argument(
        "-d",
        "--init-directory",
        default=default_init_dir,
        help="Set Emacs init directory and load DIR/init.el (default: $EMACSD or $EMACS_INIT_DIR)",
    )
    p_dump.add_argument(
        "-i",
        "--init-file",
        default=os.environ.get("EMACS_INIT_FILE"),
        help="Load specified init file (default: $EMACS_INIT_FILE)",
    )
    p_dump.add_argument(
        "-Q",
        "--quick",
        action="store_true",
        help="Run without loading user init (default when neither init-directory nor init-file is specified)",
    )
    p_dump.add_argument(
        "--emacs-bin",
        default=os.environ.get("EMACS_BIN", "emacs"),
        help="Path to emacs executable (default: $EMACS_BIN or emacs)",
    )
    p_dump.add_argument(
        "-o",
        "--output",
        help="Write output to file instead of stdout",
    )
    p_dump.add_argument(
        "emacs_args",
        nargs="*",
        help="Extra arguments passed to emacs (use -- before extra args if needed)",
    )

    # Filter / format options (default mode or analyze)
    p_filter = subparsers.add_parser(
        "filter",
        help="Filter, analyze, and format keybinding dump (default when no subcommand is specified)",
        description="Filter, analyze, and format keybinding dump.",
    )
    for p in (parser, p_filter):
        p.add_argument("input", nargs="?", default="-", help="Input JSONL file or - for stdin (default: -)")
        p.add_argument("-d", "--duplicates-only", action="store_true", help="Include only sequences with >=2 keymaps")
        p.add_argument("-s", "--sequence", dest="seq_pattern", help="Filter by sequence regex pattern")
        p.add_argument("-k", "--keymap", action="append", dest="keymap_patterns", help="Filter by keymap regex pattern (can be specified multiple times; also defines TSV columns)")
        p.add_argument("-c", "--command", dest="cmd_pattern", help="Filter by command regex pattern")

        # Stats mode option
        p.add_argument(
            "--stats",
            nargs="?",
            const="both",
            choices=["sequence", "keymap", "both"],
            help="Calculate duplicate statistics summary (default target: both)",
        )
        p.add_argument("--min-count", type=int, default=2, help="Min duplicate count for sequence stats (default: 2)")
        p.add_argument("--limit", type=int, help="Max entries to output")

        # Output formatting options
        p.add_argument(
            "-f",
            "--format",
            choices=["text", "tsv", "json", "jsonl"],
            default="text",
            help="Output format (default: text)",
        )
        p.add_argument("--none-value", default="None", help="Placeholder for missing bindings in TSV matrix (default: None)")
        p.add_argument("-o", "--output", help="Write output to file instead of stdout")

    # If first arg is 'dump', parse using subparsers
    if len(sys.argv) > 1 and sys.argv[1] == "dump":
        args = parser.parse_args()
        out_f = open(args.output, "w", encoding="utf-8") if args.output else None
        try:
            rc = run_dump(
                init_dir=args.init_directory,
                init_file=args.init_file,
                quick=args.quick,
                emacs_bin=args.emacs_bin,
                extra_args=args.emacs_args,
                stdout=out_f,
            )
            if rc != 0:
                sys.exit(rc)
            return
        finally:
            if out_f:
                out_f.close()

    # Otherwise parse as filter/format command
    args, unknown = parser.parse_known_args()
    if getattr(args, "subcommand", None) == "dump":
        out_f = open(args.output, "w", encoding="utf-8") if args.output else None
        try:
            rc = run_dump(
                init_dir=args.init_directory,
                init_file=args.init_file,
                quick=args.quick,
                emacs_bin=args.emacs_bin,
                extra_args=args.emacs_args,
                stdout=out_f,
            )
            if rc != 0:
                sys.exit(rc)
            return
        finally:
            if out_f:
                out_f.close()

    collection = _load_collection(args.input)

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
