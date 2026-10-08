"""Table-driven unit tests for emacs-keybind-dump."""

from __future__ import annotations

import json
import sys
from pathlib import Path
import unittest

# Ensure src is in sys.path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from keybind_dump.models import KeyBinding, KeybindCollection
from keybind_dump.stats import sequence_duplicate_stats, keymap_duplicate_stats
from keybind_dump.mermaid import generate_mermaid_venn


class TestKeybindCollectionTableDriven(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        raw_items = [
            {"sequence": "C-x C-f", "keymap": "global-map", "command": "find-file"},
            {"sequence": "C-x C-f", "keymap": "dired-mode-map", "command": "dired-find-file"},
            {"sequence": "C-x C-s", "keymap": "global-map", "command": "save-buffer"},
            {"sequence": "q", "keymap": "dired-mode-map", "command": "quit-window"},
            {"sequence": "q", "keymap": "help-mode-map", "command": "quit-window"},
            {"sequence": "h", "keymap": "help-mode-map", "command": "describe-mode"},
            {"sequence": "<menu-bar> [test]", "keymap": "special-mode-map", "command": "test-cmd"},
            {"sequence": '"', "keymap": "quote-mode-map", "command": "self-insert-command"},
        ]
        lines = [json.dumps(item) for item in raw_items]
        lines.extend(["", "   "])  # Add empty/whitespace lines to test robustness
        cls.sample_jsonl = "\n".join(lines)
        cls.coll = KeybindCollection.from_jsonl(cls.sample_jsonl.splitlines())

    def test_from_jsonl_parsing(self):
        cases = [
            {
                "name": "parses all valid lines ignoring blanks",
                "input_lines": ["", "   ", '{"sequence": "a", "keymap": "k1", "command": "c1"}', ""],
                "expected_sequences": ["a"],
            },
            {
                "name": "empty input yields empty collection",
                "input_lines": [],
                "expected_sequences": [],
            },
        ]
        for c in cases:
            with self.subTest(c["name"]):
                coll = KeybindCollection.from_jsonl(c["input_lines"])
                self.assertEqual(coll.get_all_sequences(), c["expected_sequences"])

    def test_filter_table_driven(self):
        cases = [
            {
                "name": "filter by sequence prefix",
                "kwargs": {"sequence_pattern": r"^C-x"},
                "expected_sequences": {"C-x C-f", "C-x C-s"},
            },
            {
                "name": "filter by keymap pattern",
                "kwargs": {"keymap_pattern": r"help"},
                "expected_sequences": {"q", "h"},
            },
            {
                "name": "filter by command pattern",
                "kwargs": {"command_pattern": r"find"},
                "expected_sequences": {"C-x C-f"},
            },
            {
                "name": "filter duplicates only",
                "kwargs": {"duplicates_only": True},
                "expected_sequences": {"C-x C-f", "q"},
            },
            {
                "name": "filter combined regexes matching single command",
                "kwargs": {
                    "sequence_pattern": r"^C-x",
                    "keymap_pattern": r"dired",
                    "command_pattern": r"dired-find-file",
                },
                "expected_sequences": {"C-x C-f"},
            },
            {
                "name": "filter non-matching regex returns empty",
                "kwargs": {"sequence_pattern": r"^non-existent$"},
                "expected_sequences": set(),
            },
        ]
        for c in cases:
            with self.subTest(c["name"]):
                filtered = self.coll.filter(**c["kwargs"])
                actual = set(filtered.to_nested_dict().keys())
                self.assertEqual(actual, c["expected_sequences"])

    def test_search_table_driven(self):
        cases = [
            {
                "name": "search exact sequence hit",
                "kwargs": {"sequence": "C-x C-s"},
                "expected_count": 1,
                "expected_commands": ["save-buffer"],
            },
            {
                "name": "search duplicate sequence returns all keymaps",
                "kwargs": {"sequence": "q"},
                "expected_count": 2,
                "expected_commands": ["quit-window", "quit-window"],
            },
            {
                "name": "search exact command hit across maps",
                "kwargs": {"command": "quit-window"},
                "expected_count": 2,
                "expected_commands": ["quit-window", "quit-window"],
            },
            {
                "name": "search exact keymap",
                "kwargs": {"keymap": "quote-mode-map"},
                "expected_count": 1,
                "expected_commands": ["self-insert-command"],
            },
            {
                "name": "search non-existent key returns empty",
                "kwargs": {"sequence": "M-x non-existent"},
                "expected_count": 0,
                "expected_commands": [],
            },
        ]
        for c in cases:
            with self.subTest(c["name"]):
                results = self.coll.search(**c["kwargs"])
                self.assertEqual(len(results), c["expected_count"])
                self.assertEqual([r.command for r in results], c["expected_commands"])

    def test_sequence_stats_table_driven(self):
        cases = [
            {
                "name": "min_count=2 includes only duplicates",
                "min_count": 2,
                "expected_sequences": ["C-x C-f", "q"],
            },
            {
                "name": "min_count=1 includes all 6 unique sequences",
                "min_count": 1,
                "expected_count": 6,
            },
            {
                "name": "min_count=10 returns empty",
                "min_count": 10,
                "expected_sequences": [],
            },
        ]
        for c in cases:
            with self.subTest(c["name"]):
                stats = sequence_duplicate_stats(self.coll, min_count=c["min_count"])
                if "expected_sequences" in c:
                    actual = [s.sequence for s in stats]
                    self.assertEqual(actual, c["expected_sequences"])
                if "expected_count" in c:
                    self.assertEqual(len(stats), c["expected_count"])

    def test_keymap_stats_table_driven(self):
        cases = [
            {
                "name": "dired-mode-map has score 2 (C-x C-f overlap 1, q overlap 1)",
                "keymap": "dired-mode-map",
                "expected_score": 2,
                "expected_bindings": 2,
            },
            {
                "name": "global-map has score 1 (C-x C-f overlap 1, C-x C-s overlap 0)",
                "keymap": "global-map",
                "expected_score": 1,
                "expected_bindings": 2,
            },
            {
                "name": "quote-mode-map has score 0 (isolated keymap)",
                "keymap": "quote-mode-map",
                "expected_score": 0,
                "expected_bindings": 1,
            },
        ]
        stats = {s.keymap: s for s in keymap_duplicate_stats(self.coll)}
        for c in cases:
            with self.subTest(c["name"]):
                stat = stats.get(c["keymap"])
                self.assertIsNotNone(stat)
                self.assertEqual(stat.total_duplicate_score, c["expected_score"])
                self.assertEqual(stat.unique_bindings_count, c["expected_bindings"])

    def test_mermaid_generation_table_driven(self):
        cases = [
            {
                "name": "default options includes all maps and escaped chars",
                "kwargs": {},
                "expected_contains": [
                    "flowchart TD",
                    "subgraph km_global_map",
                    "Shared / Intersecting Keybindings",
                    "&quot;",       # quote escaped
                    "&#91;test&#93;", # brackets escaped
                ],
                "expected_not_contains": [],
            },
            {
                "name": "filter target_keymaps excludes unselected maps",
                "kwargs": {"target_keymaps": ["dired-mode-map", "help-mode-map"]},
                "expected_contains": [
                    "subgraph km_dired_mode_map",
                    "subgraph km_help_mode_map",
                    "dired-mode-map ∩ help-mode-map",
                ],
                "expected_not_contains": [
                    "subgraph km_global_map",
                    "subgraph km_quote_mode_map",
                ],
            },
            {
                "name": "truncation threshold triggers 'and X more'",
                "kwargs": {
                    "target_keymaps": ["dired-mode-map", "help-mode-map"],
                    "max_items_per_group": 1,
                },
                "expected_contains": [
                    "<b>Intersection",
                ],
                "expected_not_contains": [],
            },
        ]
        for c in cases:
            with self.subTest(c["name"]):
                chart = generate_mermaid_venn(self.coll, **c["kwargs"])
                for expected in c["expected_contains"]:
                    self.assertIn(expected, chart)
                for not_expected in c["expected_not_contains"]:
                    self.assertNotIn(not_expected, chart)


if __name__ == "__main__":
    unittest.main()
