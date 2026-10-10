"""Output formatters for keybinding collections and statistics."""

from __future__ import annotations

import csv
import io
import json
from typing import Any

from keybind_dump.models import KeybindCollection
from keybind_dump.stats import (
    KeymapDuplicateStat,
    OverallSummaryStat,
    SequenceDuplicateStat,
    keymap_duplicate_stats,
    overall_summary_stats,
    sequence_duplicate_stats,
)

# ==============================================================================
# Statistics Formatters
# ==============================================================================


def _format_stats_json(
    summary: OverallSummaryStat,
    target: str,
    seq_stats: list[SequenceDuplicateStat],
    km_stats: list[KeymapDuplicateStat],
) -> str:
    """Format duplicate statistics as compact JSON."""
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


def _format_stats_tsv(
    summary: OverallSummaryStat,
    target: str,
    seq_stats: list[SequenceDuplicateStat],
    km_stats: list[KeymapDuplicateStat],
) -> str:
    """Format duplicate statistics as TSV."""
    out = io.StringIO()
    writer = csv.writer(out, delimiter="\t", lineterminator="\n")

    def _write_sequence_tsv():
        writer.writerow(["sequence", "count", "has_conflict", "keymaps", "commands"])
        for s in seq_stats:
            cmd_repr = "; ".join(f"{km}->{cmd}" for km, cmd in sorted(s.commands.items()))
            writer.writerow([s.sequence, s.count, str(s.has_conflict), ",".join(s.keymaps), cmd_repr])

    def _write_keymap_tsv():
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

    if target == "sequence":
        _write_sequence_tsv()
    elif target == "keymap":
        _write_keymap_tsv()
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
        _write_sequence_tsv()
        writer.writerow([])
        writer.writerow(["# Keymap Duplicate Stats"])
        _write_keymap_tsv()

    return out.getvalue()


def _format_stats_text(
    summary: OverallSummaryStat,
    target: str,
    seq_stats: list[SequenceDuplicateStat],
    km_stats: list[KeymapDuplicateStat],
) -> str:
    """Format duplicate statistics as human-readable text."""
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


def format_stats(
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
        return _format_stats_json(summary, target, seq_stats, km_stats)
    elif fmt == "tsv":
        return _format_stats_tsv(summary, target, seq_stats, km_stats)
    else:
        return _format_stats_text(summary, target, seq_stats, km_stats)


# ==============================================================================
# Collection Formatters
# ==============================================================================


def _format_collection_json(
    nested: dict[str, dict[str, str]],
    limit: int | None,
) -> str:
    """Format collection as compact nested JSON mapping."""
    if limit is not None:
        nested = {seq: nested[seq] for seq in sorted(nested.keys())[:limit]}
    return json.dumps(nested, separators=(",", ":"), ensure_ascii=False) + "\n"


def _format_collection_jsonl(
    nested: dict[str, dict[str, str]],
    limit: int | None,
) -> str:
    """Format collection as JSON Lines."""
    out = io.StringIO()
    count = 0
    for seq, km_map in sorted(nested.items()):
        for km, cmd in sorted(km_map.items()):
            out.write(
                json.dumps(
                    {"sequence": seq, "keymap": km, "command": cmd},
                    separators=(",", ":"),
                    ensure_ascii=False,
                )
                + "\n"
            )
            count += 1
            if limit and count >= limit:
                return out.getvalue()
    return out.getvalue()


def _format_collection_text(
    nested: dict[str, dict[str, str]],
    limit: int | None,
) -> str:
    """Format collection as human-readable text."""
    lines = []
    for seq, km_map in sorted(nested.items()):
        for km, cmd in sorted(km_map.items()):
            lines.append(f"[{seq}] {km} -> {cmd}")
            if limit and len(lines) >= limit:
                break
        if limit and len(lines) >= limit:
            break
    return "\n".join(lines) + ("\n" if lines else "")


def format_collection(
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
        return _format_collection_json(nested, limit)
    elif fmt == "jsonl":
        return _format_collection_jsonl(nested, limit)
    else:
        return _format_collection_text(nested, limit)
