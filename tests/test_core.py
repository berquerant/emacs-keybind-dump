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
                "name": "dired-mode-map has 2 bindings, both shared (C-x C-f, q)",
                "keymap": "dired-mode-map",
                "expected_score": 2,
                "expected_total": 2,
                "expected_shared": 2,
                "expected_exclusive": 0,
            },
            {
                "name": "global-map has 2 bindings, 1 shared (C-x C-f) and 1 exclusive (C-x C-s)",
                "keymap": "global-map",
                "expected_score": 1,
                "expected_total": 2,
                "expected_shared": 1,
                "expected_exclusive": 1,
            },
            {
                "name": "quote-mode-map has 1 exclusive binding, 0 shared",
                "keymap": "quote-mode-map",
                "expected_score": 0,
                "expected_total": 1,
                "expected_shared": 0,
                "expected_exclusive": 1,
            },
        ]
        stats = {s.keymap: s for s in keymap_duplicate_stats(self.coll)}
        for c in cases:
            with self.subTest(c["name"]):
                stat = stats.get(c["keymap"])
                self.assertIsNotNone(stat)
                self.assertEqual(stat.total_duplicate_score, c["expected_score"])
                self.assertEqual(stat.total_bindings, c["expected_total"])
                self.assertEqual(stat.shared_bindings, c["expected_shared"])
                self.assertEqual(stat.exclusive_bindings, c["expected_exclusive"])

    def test_tsv_generation_table_driven(self):
        cases = [
            {
                "name": "default options includes all keymaps header and rows",
                "kwargs": {},
                "expected_rows": [
                    ["keybind", "dired-mode-map", "global-map", "help-mode-map", "quote-mode-map", "special-mode-map"],
                    ['""""', "None", "None", "None", "self-insert-command", "None"],
                    ["<menu-bar> [test]", "None", "None", "None", "None", "test-cmd"],
                    ["C-x C-f", "dired-find-file", "find-file", "None", "None", "None"],
                    ["C-x C-s", "None", "save-buffer", "None", "None", "None"],
                    ["h", "None", "None", "describe-mode", "None", "None"],
                    ["q", "quit-window", "None", "quit-window", "None", "None"],
                ],
            },
            {
                "name": "filter target_keymaps limits columns to specified keymaps",
                "kwargs": {"target_keymaps": ["global-map", "dired-mode-map"]},
                "expected_rows": [
                    ["keybind", "global-map", "dired-mode-map"],
                    ["C-x C-f", "find-file", "dired-find-file"],
                    ["C-x C-s", "save-buffer", "None"],
                    ["q", "None", "quit-window"],
                ],
            },
            {
                "name": "duplicates_only includes only multi-keymap sequences",
                "kwargs": {"duplicates_only": True},
                "expected_rows": [
                    ["keybind", "dired-mode-map", "global-map", "help-mode-map", "quote-mode-map", "special-mode-map"],
                    ["C-x C-f", "dired-find-file", "find-file", "None", "None", "None"],
                    ["q", "quit-window", "None", "quit-window", "None", "None"],
                ],
            },
            {
                "name": "custom none_value is respected",
                "kwargs": {"target_keymaps": ["global-map", "dired-mode-map"], "none_value": "-"},
                "expected_rows": [
                    ["keybind", "global-map", "dired-mode-map"],
                    ["C-x C-s", "save-buffer", "-"],
                    ["q", "-", "quit-window"],
                ],
            },
        ]
        for c in cases:
            with self.subTest(c["name"]):
                tsv_str = self.coll.to_tsv(**c["kwargs"])
                lines = [line.split("\t") for line in tsv_str.strip().split("\n")]
                for expected_row in c["expected_rows"]:
                    self.assertIn(expected_row, lines)

    def test_cli_format_stats(self):
        from keybind_dump.cli import _format_stats, _format_collection
        # JSON format stats
        json_out = _format_stats(self.coll, target="both", fmt="json", min_count=2, limit=None)
        data = json.loads(json_out)
        self.assertIn("summary", data)
        self.assertIn("sequences", data)
        self.assertIn("keymaps", data)
        self.assertEqual(data["sequences"][0]["sequence"], "C-x C-f")
        self.assertTrue(data["sequences"][0]["has_conflict"])
        self.assertIn("top_overlaps", data["keymaps"][0])

        # TSV format stats
        tsv_out = _format_stats(self.coll, target="sequence", fmt="tsv", min_count=2, limit=None)
        self.assertIn("sequence\tcount\thas_conflict\tkeymaps\tcommands", tsv_out)

        # Text format stats
        text_out = _format_stats(self.coll, target="both", fmt="text", min_count=2, limit=None)
        self.assertIn("=== Summary Overview ===", text_out)
        self.assertIn("=== Sequence Duplicate Stats ===", text_out)
        self.assertIn("=== Keymap Duplicate Stats ===", text_out)
        self.assertIn("exclusive:", text_out)
        self.assertIn("top overlaps:", text_out)

    def test_cli_format_collection(self):
        from keybind_dump.cli import _format_collection
        # JSON format
        json_out = _format_collection(self.coll, fmt="json", target_keymaps=None, none_value="None", duplicates_only=False, limit=None)
        data = json.loads(json_out)
        self.assertIn("C-x C-f", data)

        # JSONL format
        jsonl_out = _format_collection(self.coll, fmt="jsonl", target_keymaps=None, none_value="None", duplicates_only=False, limit=2)
        lines = [json.loads(line) for line in jsonl_out.strip().split("\n")]
        self.assertEqual(len(lines), 2)

        # Text format
        text_out = _format_collection(self.coll, fmt="text", target_keymaps=None, none_value="None", duplicates_only=False, limit=None)
        self.assertIn("[C-x C-f] dired-mode-map -> dired-find-file", text_out)

    def test_dumper_build_emacs_cmd(self):
        from keybind_dump.dumper import build_emacs_cmd

        # 1. Quick mode (-Q)
        cmd_quick = build_emacs_cmd(quick=True)
        self.assertIn("-Q", cmd_quick)
        self.assertIn("keybind-dump-jsonl", cmd_quick)

        # 2. Neither init_dir nor init_file -> default -Q
        cmd_default = build_emacs_cmd()
        self.assertIn("-Q", cmd_default)

        # 3. With init_dir
        cmd_dir = build_emacs_cmd(init_dir="/tmp/test-emacs.d")
        self.assertIn("--init-directory", cmd_dir)
        self.assertNotIn("-Q", cmd_dir)

        # 4. With init_file
        cmd_file = build_emacs_cmd(init_file="/tmp/test-init.el")
        self.assertIn("-l", cmd_file)
        self.assertNotIn("-Q", cmd_file)


if __name__ == "__main__":
    unittest.main()
