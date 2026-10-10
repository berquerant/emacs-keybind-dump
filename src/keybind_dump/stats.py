"""Statistics calculations for keybinding collections."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from keybind_dump.models import KeybindCollection


@dataclass(frozen=True)
class SequenceDuplicateStat:
    """Duplicate statistics for an individual key sequence across keymaps.

    Attributes:
        sequence: The key sequence string (e.g. 'C-x C-f').
        count: Number of keymaps that bind this sequence.
        keymaps: Alphabetical list of keymap names binding this sequence.
        distinct_commands_count: Number of unique commands assigned across keymaps.
        commands: Mapping of keymap name to assigned command string.
        has_conflict: True if different keymaps bind different commands to this sequence
            (indicating a behavioral collision when active keymaps override each other).
            False if all keymaps bind the exact same command.
    """
    sequence: str
    count: int
    keymaps: list[str]
    distinct_commands_count: int
    commands: dict[str, str]  # keymap -> command
    has_conflict: bool  # True if different keymaps bind different commands to this sequence


@dataclass(frozen=True)
class KeymapDuplicateStat:
    """Statistical summary of duplicate bindings and overlaps for a specific keymap.

    Attributes:
        keymap: Name of the keymap (e.g. 'global-map').
        total_bindings: Total number of bindings registered in this keymap.
        exclusive_bindings: Number of bindings that are unique to this keymap.
        shared_bindings: Number of bindings that overlap with at least one other keymap.
        conflict_rate: Proportion of shared bindings relative to total (`shared / total`).
        total_duplicate_score: Sum of duplicate penalties (for each shared key: `overlap_count - 1`).
        top_overlaps: List of tuples `(other_keymap, shared_key_count)` sorted descending.
    """
    keymap: str
    total_bindings: int
    exclusive_bindings: int
    shared_bindings: int
    conflict_rate: float  # shared / total (0.0 ~ 1.0)
    total_duplicate_score: int
    top_overlaps: list[tuple[str, int]]  # list of (other_keymap, shared_key_count)


@dataclass(frozen=True)
class OverallSummaryStat:
    """High-level summary metrics across an entire keybinding collection."""
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
    """Calculate comprehensive duplicate and overlap statistics per keymap.

    Metrics calculated per keymap:
    - total: Total keybinding count in the keymap.
    - exclusive: Keys bound uniquely in this keymap (no other keymap defines this key).
    - shared: Keys also defined in at least one other keymap.
    - conflict_rate: `shared / total` (0.0 to 1.0).
    - total_duplicate_score: Sum of duplicate penalties $\\sum (k - 1)$ where $k$ is the
      number of keymaps claiming that key.
    - top_overlaps: The top $N$ other keymaps sharing the most keys with this keymap.

    Returned list is sorted descending by shared_bindings, total_duplicate_score, then total_bindings.
    """
    nested = collection.to_nested_dict()

    km_totals: Counter[str] = Counter()
    km_exclusive: Counter[str] = Counter()
    km_shared: Counter[str] = Counter()
    km_scores: Counter[str] = Counter()

    # overlap matrix: (kmA, kmB) -> shared count
    overlaps: dict[str, Counter[str]] = defaultdict(Counter)

    for km_map in nested.values():
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
