"""Statistics calculations for keybinding collections."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING, Dict, List, Tuple

if TYPE_CHECKING:
    from keybind_dump.models import KeybindCollection


@dataclass(frozen=True)
class SequenceDuplicateStat:
    sequence: str
    count: int
    keymaps: list[str]
    distinct_commands_count: int
    commands: dict[str, str]  # keymap -> command
    has_conflict: bool  # True if different keymaps bind different commands to this sequence


@dataclass(frozen=True)
class KeymapDuplicateStat:
    keymap: str
    total_bindings: int
    exclusive_bindings: int
    shared_bindings: int
    conflict_rate: float  # shared / total (0.0 ~ 1.0)
    total_duplicate_score: int
    top_overlaps: list[tuple[str, int]]  # list of (other_keymap, shared_key_count)


@dataclass(frozen=True)
class OverallSummaryStat:
    total_records: int
    unique_sequences: int
    unique_keymaps: int
    shared_sequences: int
    sequence_conflict_rate: float  # shared_sequences / unique_sequences


def overall_summary_stats(collection: KeybindCollection) -> OverallSummaryStat:
    """Calculate overall summary across the collection."""
    nested = collection.to_nested_dict()
    total_records = sum(len(km_map) for km_map in nested.values())
    unique_sequences = len(nested)

    keymaps = set()
    shared_sequences = 0
    for km_map in nested.values():
        keymaps.update(km_map.keys())
        if len(km_map) > 1:
            shared_sequences += 1

    rate = (shared_sequences / unique_sequences) if unique_sequences > 0 else 0.0
    return OverallSummaryStat(
        total_records=total_records,
        unique_sequences=unique_sequences,
        unique_keymaps=len(keymaps),
        shared_sequences=shared_sequences,
        sequence_conflict_rate=rate,
    )


def sequence_duplicate_stats(
    collection: KeybindCollection, min_count: int = 1
) -> list[SequenceDuplicateStat]:
    """Calculate duplicate frequency per sequence (sorted descending by count)."""
    nested = collection.to_nested_dict()
    stats = []
    for seq, km_map in nested.items():
        cnt = len(km_map)
        if cnt >= min_count:
            distinct_cmds = set(km_map.values())
            has_conflict = len(distinct_cmds) > 1
            stats.append(
                SequenceDuplicateStat(
                    sequence=seq,
                    count=cnt,
                    keymaps=sorted(km_map.keys()),
                    distinct_commands_count=len(distinct_cmds),
                    commands=dict(km_map),
                    has_conflict=has_conflict,
                )
            )
    return sorted(stats, key=lambda s: (-s.count, s.sequence))


def keymap_duplicate_stats(
    collection: KeybindCollection, top_overlaps_limit: int = 3
) -> list[KeymapDuplicateStat]:
    """Calculate comprehensive duplicate statistics per keymap."""
    nested = collection.to_nested_dict()

    km_totals: Counter[str] = Counter()
    km_exclusive: Counter[str] = Counter()
    km_shared: Counter[str] = Counter()
    km_scores: Counter[str] = Counter()

    # overlap matrix: (kmA, kmB) -> shared count
    overlaps: dict[str, Counter[str]] = defaultdict(Counter)

    for seq, km_map in nested.items():
        kms = sorted(km_map.keys())
        is_shared = len(kms) > 1
        score = len(kms) - 1

        for km in kms:
            km_totals[km] += 1
            km_scores[km] += score
            if is_shared:
                km_shared[km] += 1
            else:
                km_exclusive[km] += 1

        if is_shared:
            for i, km1 in enumerate(kms):
                for km2 in kms[i + 1 :]:
                    overlaps[km1][km2] += 1
                    overlaps[km2][km1] += 1

    stats = []
    for km, total in km_totals.items():
        exclusive = km_exclusive[km]
        shared = km_shared[km]
        conflict_rate = (shared / total) if total > 0 else 0.0
        score = km_scores[km]

        top_ov = overlaps[km].most_common(top_overlaps_limit)
        stats.append(
            KeymapDuplicateStat(
                keymap=km,
                total_bindings=total,
                exclusive_bindings=exclusive,
                shared_bindings=shared,
                conflict_rate=conflict_rate,
                total_duplicate_score=score,
                top_overlaps=top_ov,
            )
        )

    # Sort descending by shared_bindings, total_duplicate_score, then total_bindings
    return sorted(
        stats,
        key=lambda s: (
            -s.shared_bindings,
            -s.total_duplicate_score,
            -s.total_bindings,
            s.keymap,
        ),
    )
