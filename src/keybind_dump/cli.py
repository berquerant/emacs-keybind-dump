"""CLI entry point for keybind-dump."""

from __future__ import annotations

import argparse
import json
import os
import signal
import sys
from typing import List, Optional

from keybind_dump.mermaid import generate_mermaid_venn
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


def cmd_transform(args: argparse.Namespace) -> None:
    collection = _load_collection(args.input)
    if args.duplicates_only:
        data = collection.duplicates()
    else:
        data = collection.to_nested_dict()
    json.dump(data, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")


def cmd_duplicates(args: argparse.Namespace) -> None:
    collection = _load_collection(args.input)
    dups = collection.duplicates()
    if args.format == "json":
        json.dump(dups, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
    else:
        for seq, km_map in sorted(dups.items()):
            kms = ", ".join(f"{k} -> {c}" for k, c in sorted(km_map.items()))
            print(f"[{seq}] ({len(km_map)} maps): {kms}")


def cmd_stats(args: argparse.Namespace) -> None:
    collection = _load_collection(args.input)
    if args.target in ("sequence", "both"):
        seq_stats = sequence_duplicate_stats(collection, min_count=args.min_count)
        if args.limit:
            seq_stats = seq_stats[: args.limit]
        print("=== Sequence Duplicate Stats ===")
        for s in seq_stats:
            print(f"{s.count:3d} keymaps: '{s.sequence}' (maps: {', '.join(s.keymaps)})")

    if args.target in ("keymap", "both"):
        km_stats = keymap_duplicate_stats(collection)
        if args.limit:
            km_stats = km_stats[: args.limit]
        print("\n=== Keymap Total Duplicate Score Stats ===")
        for k in km_stats:
            print(
                f"score: {k.total_duplicate_score:4d} (total bindings: {k.unique_bindings_count:4d}) - {k.keymap}"
            )


def cmd_filter(args: argparse.Namespace) -> None:
    collection = _load_collection(args.input)
    filtered = collection.filter(
        sequence_pattern=args.seq_regex,
        keymap_pattern=args.keymap_regex,
        command_pattern=args.command_regex,
        duplicates_only=args.duplicates_only,
    )
    if args.format == "json":
        json.dump(filtered.to_nested_dict(), sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
    elif args.format == "jsonl":
        for seq, km_map in filtered.to_nested_dict().items():
            for km, cmd in km_map.items():
                sys.stdout.write(
                    json.dumps({"sequence": seq, "keymap": km, "command": cmd}, ensure_ascii=False)
                    + "\n"
                )
    else:
        for seq, km_map in sorted(filtered.to_nested_dict().items()):
            for km, cmd in sorted(km_map.items()):
                print(f"[{seq}] {km} -> {cmd}")


def cmd_search(args: argparse.Namespace) -> None:
    collection = _load_collection(args.input)
    results = collection.search(
        sequence=args.sequence,
        keymap=args.keymap,
        command=args.command,
    )
    if args.format == "json":
        json.dump([b.to_dict() for b in results], sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
    else:
        for b in results:
            print(f"[{b.sequence}] {b.keymap} -> {b.command}")


def cmd_mermaid(args: argparse.Namespace) -> None:
    collection = _load_collection(args.input)
    target_kms = args.keymap if args.keymap else None
    chart = generate_mermaid_venn(
        collection,
        target_keymaps=target_kms,
        max_items_per_group=args.max_items,
    )
    print(chart)


def main() -> None:
    # Handle broken pipe smoothly when stdout is closed early (e.g. piped to head)
    if hasattr(signal, "SIGPIPE"):
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)

    parser = argparse.ArgumentParser(
        prog="keybind-dump",
        description="Emacs keybinding analyzer, stats, query, and Venn-like Mermaid visualizer",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # transform
    p_trans = subparsers.add_parser("transform", help="Transform JSONL into {sequence: {keymap: command}}")
    p_trans.add_argument("input", nargs="?", default="-", help="Input JSONL file or - for stdin")
    p_trans.add_argument("--duplicates-only", action="store_true", help="Include only sequences with >=2 keymaps")
    p_trans.set_defaults(func=cmd_transform)

    # duplicates
    p_dups = subparsers.add_parser("duplicates", help="Display duplicate keybindings across keymaps")
    p_dups.add_argument("input", nargs="?", default="-", help="Input JSONL file or - for stdin")
    p_dups.add_argument("--format", choices=["text", "json"], default="text", help="Output format")
    p_dups.set_defaults(func=cmd_duplicates)

    # stats
    p_stats = subparsers.add_parser("stats", help="Compute duplicate statistics")
    p_stats.add_argument("input", nargs="?", default="-", help="Input JSONL file or - for stdin")
    p_stats.add_argument("--target", choices=["sequence", "keymap", "both"], default="both")
    p_stats.add_argument("--min-count", type=int, default=2, help="Min duplicate count for sequence stats")
    p_stats.add_argument("--limit", type=int, default=20, help="Max entries to display")
    p_stats.set_defaults(func=cmd_stats)

    # filter
    p_filter = subparsers.add_parser("filter", help="Filter keybindings by regex or conditions")
    p_filter.add_argument("input", nargs="?", default="-", help="Input JSONL file or - for stdin")
    p_filter.add_argument("--seq-regex", help="Filter by sequence regex")
    p_filter.add_argument("--keymap-regex", help="Filter by keymap regex")
    p_filter.add_argument("--command-regex", help="Filter by command regex")
    p_filter.add_argument("--duplicates-only", action="store_true", help="Keep only duplicates")
    p_filter.add_argument("--format", choices=["text", "json", "jsonl"], default="text")
    p_filter.set_defaults(func=cmd_filter)

    # search
    p_search = subparsers.add_parser("search", help="Search keybindings by sequence, keymap, or command")
    p_search.add_argument("input", nargs="?", default="-", help="Input JSONL file or - for stdin")
    p_search.add_argument("--sequence", help="Exact sequence")
    p_search.add_argument("--keymap", help="Exact keymap name")
    p_search.add_argument("--command", help="Exact command name")
    p_search.add_argument("--format", choices=["text", "json"], default="text")
    p_search.set_defaults(func=cmd_search)

    # mermaid
    p_mermaid = subparsers.add_parser("mermaid", help="Generate Venn-like Mermaid diagram")
    p_mermaid.add_argument("input", nargs="?", default="-", help="Input JSONL file or - for stdin")
    p_mermaid.add_argument("--keymap", action="append", help="Specific keymap(s) to include")
    p_mermaid.add_argument("--max-items", type=int, default=30, help="Max keybindings to show per group")
    p_mermaid.set_defaults(func=cmd_mermaid)

    args = parser.parse_args()
    try:
        args.func(args)
    except BrokenPipeError:
        try:
            devnull = os.open(os.devnull, os.O_WRONLY)
            os.dup2(devnull, sys.stdout.fileno())
        except OSError:
            pass
        sys.exit(141)


if __name__ == "__main__":
    main()
