"""Statistics calculations for keybinding collections."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, List, Tuple

if TYPE_CHECKING:
    from keybind_dump.models import KeybindCollection


@dataclass(frozen=True)
class SequenceDuplicateStat:
    sequence: str
    count: int
    keymaps: list[str]


@dataclass(frozen=True)
class KeymapDuplicateStat:
    keymap: str
    total_duplicate_score: int
    unique_bindings_count: int


def sequence_duplicate_stats(
    collection: KeybindCollection, min_count: int = 1
) -> list[SequenceDuplicateStat]:
    """Calculate duplicate frequency per sequence (sorted descending by count)."""
    nested = collection.to_nested_dict()
    stats = []
    for seq, km_map in nested.items():
        cnt = len(km_map)
        if cnt >= min_count:
            stats.append(
                SequenceDuplicateStat(
                    sequence=seq,
                    count=cnt,
                    keymaps=sorted(km_map.keys()),
                )
            )
    return sorted(stats, key=lambda s: (-s.count, s.sequence))


def keymap_duplicate_stats(
    collection: KeybindCollection,
) -> list[KeymapDuplicateStat]:
    """Calculate total duplicate score per keymap.

    The duplicate score for a keymap is the sum of (duplicate count of seq in other keymaps)
    or number of shared sequences across all its bindings.
    Here we define duplicate score as: sum(len(km_map) - 1 for each seq belonging to keymap).
    """
    nested = collection.to_nested_dict()
    km_scores: dict[str, int] = {}
    km_bindings: dict[str, int] = {}

    for seq, km_map in nested.items():
        overlap = len(km_map) - 1
        for km in km_map.keys():
            km_scores[km] = km_scores.get(km, 0) + overlap
            km_bindings[km] = km_bindings.get(km, 0) + 1

    stats = [
        KeymapDuplicateStat(
            keymap=km,
            total_duplicate_score=score,
            unique_bindings_count=km_bindings.get(km, 0),
        )
        for km, score in km_scores.items()
    ]
    return sorted(stats, key=lambda s: (-s.total_duplicate_score, -s.unique_bindings_count, s.keymap))
