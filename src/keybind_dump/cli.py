"""CLI entry point for keybind-dump."""

from __future__ import annotations

import argparse
import os
import signal
import sys
from collections.abc import Sequence

from keybind_dump.dumper import iter_dump
from keybind_dump.formatters import format_collection, format_stats
from keybind_dump.models import KeybindCollection

# Re-export internal aliases for backwards-compatibility with tests/external imports
_format_stats = format_stats
_format_collection = format_collection


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
    # 1. Direct Emacs batch dump execution
    if dump or (file_path is None and sys.stdin.isatty()):
        lines = iter_dump(
            init_dir=init_dir,
            init_file=init_file,
            quick=quick,
            emacs_bin=emacs_bin,
            verbose=verbose,
        )
        return KeybindCollection.from_jsonl(lines)

    # 2. Designated file input
    if file_path and file_path != "-":
        with open(file_path, "r", encoding="utf-8") as f:
            return KeybindCollection.from_jsonl(f)

    # 3. Standard input (piped)
    if not sys.stdin.isatty():
        return KeybindCollection.from_jsonl(sys.stdin)

    # 4. Interactive fallback to direct dump
    lines = iter_dump(
        init_dir=init_dir,
        init_file=init_file,
        quick=quick,
        emacs_bin=emacs_bin,
        verbose=verbose,
    )
    return KeybindCollection.from_jsonl(lines)


def build_parser() -> argparse.ArgumentParser:
    """Build and configure the command-line argument parser."""
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
    g_filter.add_argument(
        "-D", "--duplicates-only", action="store_true", help="Include only sequences with >=2 keymaps"
    )
    g_filter.add_argument("-s", "--sequence", dest="seq_pattern", help="Filter by sequence regex pattern")
    g_filter.add_argument(
        "-k",
        "--keymap",
        action="append",
        dest="keymap_patterns",
        help="Filter by keymap regex pattern (can be specified multiple times; also defines TSV columns)",
    )
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
    g_stats.add_argument(
        "--min-count", type=int, default=2, help="Min duplicate count for sequence stats (default: 2)"
    )
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
    g_fmt.add_argument(
        "--none-value", default="None", help="Placeholder for missing bindings in TSV matrix (default: None)"
    )
    g_fmt.add_argument("-o", "--output", help="Write output to file instead of stdout")

    return parser


def run_cli(args_list: Sequence[str] | None = None) -> None:
    """Execute CLI workflow with optional argument list."""
    if hasattr(signal, "SIGPIPE"):
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)

    parser = build_parser()
    args = parser.parse_args(args_list)

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
        km_pattern = (
            f"^({'|'.join(args.keymap_patterns)})$"
            if len(args.keymap_patterns) > 1
            else args.keymap_patterns[0]
        )

    filtered = collection.filter(
        sequence_pattern=args.seq_pattern,
        keymap_pattern=km_pattern,
        command_pattern=args.cmd_pattern,
        duplicates_only=args.duplicates_only,
    )

    if args.stats:
        output_str = format_stats(
            filtered,
            target=args.stats,
            fmt=args.format,
            min_count=args.min_count,
            limit=args.limit,
        )
    else:
        output_str = format_collection(
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


def main() -> None:
    """Entry point for command execution."""
    run_cli()


if __name__ == "__main__":
    main()
