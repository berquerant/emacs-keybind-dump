"""Mermaid Venn-like diagram generator for keybinding collections."""

from __future__ import annotations

import html
from collections import defaultdict
from typing import TYPE_CHECKING, Dict, List, Set, Tuple

if TYPE_CHECKING:
    from keybind_dump.models import KeybindCollection


def _sanitize_id(name: str) -> str:
    """Sanitize string to valid Mermaid identifier."""
    res = "".join(c if c.isalnum() else "_" for c in name)
    if not res or res[0].isdigit():
        res = "id_" + res
    return res


def _escape_label(text: str) -> str:
    """Escape characters for safe Mermaid node labels enclosed in double quotes."""
    return (
        html.escape(text, quote=True)
        .replace('"', "&quot;")
        .replace("[", "&#91;")
        .replace("]", "&#93;")
    )


def generate_mermaid_venn(
    collection: KeybindCollection,
    target_keymaps: list[str] | None = None,
    max_items_per_group: int = 30,
) -> str:
    """Generate Mermaid flowchart visualizing Venn-like overlapping keybindings.

    - keymaps are represented as subgraphs.
    - sequences shared by keymaps A, B, ... are placed in an intersection node/subgraph.
    - pure elements of a single keymap are placed in its own exclusive node/subgraph.
    """
    nested = collection.to_nested_dict()

    # Filter by target_keymaps if provided
    selected_maps = set(target_keymaps) if target_keymaps else None

    # Group sequences by the exact set of keymaps they belong to: frozenset(km_list) -> list[seq]
    groups: dict[frozenset[str], list[str]] = defaultdict(list)

    all_maps: set[str] = set()

    for seq, km_map in nested.items():
        kms = set(km_map.keys())
        if selected_maps:
            kms = kms.intersection(selected_maps)
            if not kms:
                continue
        all_maps.update(kms)
        groups[frozenset(kms)].append(seq)

    lines: list[str] = [
        "flowchart TD",
        "  %% Keymap Venn diagram representation",
    ]

    # Subgraph for each keymap
    sorted_maps = sorted(all_maps)
    for km in sorted_maps:
        km_id = f"km_{_sanitize_id(km)}"
        km_title = _escape_label(km)
        lines.append(f'  subgraph {km_id}["Keymap: {km_title}"]')

        # Pure items exclusive to this keymap
        pure_seqs = sorted(groups.get(frozenset([km]), []))
        if pure_seqs:
            disp_seqs = pure_seqs[:max_items_per_group]
            extra = len(pure_seqs) - len(disp_seqs)
            body = "<br/>".join(_escape_label(s) for s in disp_seqs)
            if extra > 0:
                body += f"<br/><i>... and {extra} more</i>"
            exclusive_id = f"{km_id}_exclusive"
            lines.append(f'    {exclusive_id}["<b>[Exclusive]</b><br/>{body}"]')
        else:
            lines.append(f'    {km_id}_empty["(No exclusive keys)"]')

        lines.append("  end")

    # Intersections (sets of keymaps with size >= 2)
    intersection_groups = [
        (sorted(kms), seqs)
        for kms, seqs in groups.items()
        if len(kms) >= 2
    ]
    # Sort by group size, then names
    intersection_groups.sort(key=lambda item: (-len(item[0]), item[0]))

    if intersection_groups:
        lines.append('  subgraph Intersections["Shared / Intersecting Keybindings"]')
        for idx, (kms, seqs) in enumerate(intersection_groups):
            inter_id = f"inter_{idx}"
            disp_seqs = sorted(seqs)[:max_items_per_group]
            extra = len(seqs) - len(disp_seqs)
            km_labels = " ∩ ".join(_escape_label(k) for k in kms)
            body = "<br/>".join(_escape_label(s) for s in disp_seqs)
            if extra > 0:
                body += f"<br/><i>... and {extra} more</i>"
            lines.append(
                f'    {inter_id}["<b>Intersection ({km_labels})</b><br/>{body}"]'
            )
            # Connect the intersection node to all participating keymap subgraphs
            for km in kms:
                km_id = f"km_{_sanitize_id(km)}"
                lines.append(f"    {inter_id} -.-> {km_id}")
        lines.append("  end")

    return "\n".join(lines)
