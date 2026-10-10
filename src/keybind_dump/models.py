"""Keybind dump models and collection classes."""

from __future__ import annotations

import csv
import io
import json
import re
from dataclasses import dataclass
from typing import Dict, Iterable, Iterator, List, Optional, Set, Tuple


@dataclass(frozen=True)
class KeyBinding:
    sequence: str
    keymap: str
    command: str

    def to_dict(self) -> dict[str, str]:
        return {
            "sequence": self.sequence,
            "keymap": self.keymap,
            "command": self.command,
        }


class KeybindCollection:
    """Manages raw and nested keybinding mappings."""

    def __init__(self, bindings: Optional[Iterable[KeyBinding]] = None) -> None:
        # nested structure: {sequence: {keymap: command}}
        self._seq_map: dict[str, dict[str, str]] = {}
        if bindings:
            for b in bindings:
                self.add(b)

    def add(self, binding: KeyBinding) -> None:
        if binding.sequence not in self._seq_map:
            self._seq_map[binding.sequence] = {}
        self._seq_map[binding.sequence][binding.keymap] = binding.command

    @classmethod
    def from_jsonl(cls, lines: Iterable[str]) -> KeybindCollection:
        bindings = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            data = json.loads(line)
            bindings.append(
                KeyBinding(
                    sequence=data["sequence"],
                    keymap=data["keymap"],
                    command=data["command"],
                )
            )
        return cls(bindings)

    def to_nested_dict(self) -> dict[str, dict[str, str]]:
        """Return {sequence: {keymap: command}} structure."""
        return {seq: dict(km_map) for seq, km_map in self._seq_map.items()}

    def get_all_sequences(self) -> list[str]:
        return sorted(self._seq_map.keys())

    def get_all_keymaps(self) -> list[str]:
        keymaps: Set[str] = set()
        for km_map in self._seq_map.values():
            keymaps.update(km_map.keys())
        return sorted(keymaps)

    def get_all_commands(self) -> list[str]:
        commands: Set[str] = set()
        for km_map in self._seq_map.values():
            commands.update(km_map.values())
        return sorted(commands)

    def duplicates(self) -> dict[str, dict[str, str]]:
        """Return sequences that belong to 2 or more keymaps."""
        return {
            seq: dict(km_map)
            for seq, km_map in self._seq_map.items()
            if len(km_map) > 1
        }

    def filter(
        self,
        sequence_pattern: Optional[str] = None,
        keymap_pattern: Optional[str] = None,
        command_pattern: Optional[str] = None,
        duplicates_only: bool = False,
    ) -> KeybindCollection:
        """Filter bindings using regular expressions and criteria."""
        seq_re = re.compile(sequence_pattern) if sequence_pattern else None
        km_re = re.compile(keymap_pattern) if keymap_pattern else None
        cmd_re = re.compile(command_pattern) if command_pattern else None

        filtered = KeybindCollection()
        for seq, km_map in self._seq_map.items():
            if duplicates_only and len(km_map) <= 1:
                continue
            if seq_re and not seq_re.search(seq):
                continue

            for km, cmd in km_map.items():
                if km_re and not km_re.search(km):
                    continue
                if cmd_re and not cmd_re.search(cmd):
                    continue
                filtered.add(KeyBinding(sequence=seq, keymap=km, command=cmd))
        return filtered

    def search(
        self,
        sequence: Optional[str] = None,
        keymap: Optional[str] = None,
        command: Optional[str] = None,
    ) -> list[KeyBinding]:
        """Search bindings by exact sequence, keymap, or command match."""
        results: list[KeyBinding] = []
        for seq, km_map in self._seq_map.items():
            if sequence is not None and seq != sequence:
                continue
            for km, cmd in km_map.items():
                if keymap is not None and km != keymap:
                    continue
                if command is not None and cmd != command:
                    continue
                results.append(KeyBinding(sequence=seq, keymap=km, command=cmd))
        return sorted(results, key=lambda b: (b.sequence, b.keymap, b.command))

    def to_tsv(
        self,
        target_keymaps: Optional[list[str]] = None,
        none_value: str = "None",
        duplicates_only: bool = False,
    ) -> str:
        """Export keybinding matrix as TSV.

        - Header: keybind, followed by keymap names.
        - Rows: keybind value, followed by command for each keymap (or none_value if missing).
        """
        if target_keymaps:
            keymaps = list(target_keymaps)
        else:
            keymaps = self.get_all_keymaps()

        output = io.StringIO()
        writer = csv.writer(output, delimiter="\t", lineterminator="\n")

        # Header row
        writer.writerow(["keybind", *keymaps])

        # Data rows
        for seq in self.get_all_sequences():
            km_map = self._seq_map[seq]
            if duplicates_only and len(km_map) <= 1:
                continue

            # If target_keymaps are filtered, check if at least one target keymap is present when filtering
            if target_keymaps and not any(km in km_map for km in target_keymaps):
                continue

            row = [seq]
            for km in keymaps:
                row.append(km_map.get(km, none_value))
            writer.writerow(row)

        return output.getvalue()
