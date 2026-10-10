"""Table-driven unit tests for emacs-keybind-dump."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

# Ensure src is in sys.path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from keybind_dump.models import KeybindCollection
from keybind_dump.stats import keymap_duplicate_stats, sequence_duplicate_stats


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
        from keybind_dump.cli import _format_stats
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
        # JSON format with and without limit
        json_out = _format_collection(self.coll, fmt="json", target_keymaps=None, none_value="None", duplicates_only=False, limit=None)
        data = json.loads(json_out)
        self.assertIn("C-x C-f", data)
        self.assertGreater(len(data), 2)

        json_out_limited = _format_collection(self.coll, fmt="json", target_keymaps=None, none_value="None", duplicates_only=False, limit=2)
        data_limited = json.loads(json_out_limited)
        self.assertEqual(len(data_limited), 2)

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

        # 5. With eval_before_dump and load_before_dump
        cmd_hooks = build_emacs_cmd(
            eval_before_dump=["(require 'org)", "(message \"loaded\")"],
            load_before_dump=["/tmp/setup.el"],
        )
        self.assertIn("--eval", cmd_hooks)
        self.assertIn("(require 'org)", cmd_hooks)
        self.assertIn("/tmp/setup.el", cmd_hooks)

        # Ensure keybind-dump.el is loaded before user hooks/evals
        idx_pkg = next(i for i, arg in enumerate(cmd_hooks) if "keybind-dump.el" in arg)
        idx_load = cmd_hooks.index("/tmp/setup.el")
        idx_eval = cmd_hooks.index("(require 'org)")
        self.assertLess(idx_pkg, idx_load)
        self.assertLess(idx_pkg, idx_eval)

    def test_cli_multiple_pattern_options(self):
        from keybind_dump.cli import _combine_regex_patterns, build_parser

        parser = build_parser()
        args = parser.parse_args([
            "-s", "^C-x", "-s", "^q$",
            "-k", "global-map", "-k", "dired-mode-map",
            "-c", "find", "-c", "save",
        ])

        self.assertEqual(args.seq_patterns, ["^C-x", "^q$"])
        self.assertEqual(args.keymap_patterns, ["global-map", "dired-mode-map"])
        self.assertEqual(args.cmd_patterns, ["find", "save"])

        # Check combined regexes
        combined_seq = _combine_regex_patterns(args.seq_patterns)
        combined_cmd = _combine_regex_patterns(args.cmd_patterns)
        self.assertEqual(combined_seq, "(?:^C-x|^q$)")
        self.assertEqual(combined_cmd, "(?:find|save)")

        # Verify collection filtering with combined pattern matches either
        filtered = self.coll.filter(sequence_pattern=combined_seq)
        self.assertEqual(set(filtered.to_nested_dict().keys()), {"C-x C-f", "C-x C-s", "q"})

    def test_models_additional_coverage(self):
        from keybind_dump.models import KeyBinding

        binding = KeyBinding(sequence="C-c a", keymap="org-mode-map", command="org-agenda")
        self.assertEqual(
            binding.to_dict(),
            {"sequence": "C-c a", "keymap": "org-mode-map", "command": "org-agenda"},
        )

        all_cmds = self.coll.get_all_commands()
        self.assertIn("find-file", all_cmds)
        self.assertIn("quit-window", all_cmds)

        dups = self.coll.duplicates()
        self.assertIn("C-x C-f", dups)
        self.assertIn("q", dups)
        self.assertNotIn("C-x C-s", dups)

    def test_format_stats_keymap_tsv(self):
        from keybind_dump.formatters import format_stats

        # Test tsv output when target="keymap" exclusively
        tsv_out = format_stats(self.coll, target="keymap", fmt="tsv", min_count=1, limit=None)
        lines = tsv_out.strip().split("\n")
        self.assertEqual(
            lines[0],
            "keymap\ttotal_bindings\texclusive_bindings\tshared_bindings\tconflict_rate\ttotal_duplicate_score\ttop_overlaps",
        )
        self.assertGreater(len(lines), 1)

    def test_cli_load_collection_sources(self):
        import io
        import tempfile
        from unittest.mock import patch

        from keybind_dump.cli import _load_collection

        # 1. From a regular JSONL file
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as f:
            f.write('{"sequence": "C-z", "keymap": "global-map", "command": "suspend-frame"}\n')
            temp_path = f.name

        try:
            coll = _load_collection(file_path=temp_path)
            self.assertEqual(coll.get_all_sequences(), ["C-z"])
        finally:
            Path(temp_path).unlink(missing_ok=True)

        # 2. From standard input (file_path="-" or stdin piped)
        mock_stdin = io.StringIO('{"sequence": "C-a", "keymap": "global-map", "command": "move-beginning-of-line"}\n')
        with patch("sys.stdin", mock_stdin):
            mock_stdin.isatty = lambda: False  # type: ignore[method-assign]
            coll_stdin = _load_collection(file_path="-")
            self.assertEqual(coll_stdin.get_all_sequences(), ["C-a"])

        # 3. Direct dump execution via iter_dump mock
        with patch("keybind_dump.cli.iter_dump") as mock_iter:
            mock_iter.return_value = ['{"sequence": "C-b", "keymap": "k", "command": "c"}\n']
            coll_dump = _load_collection(file_path=None, dump=True)
            self.assertEqual(coll_dump.get_all_sequences(), ["C-b"])
            mock_iter.assert_called_once()

    def test_cli_run_cli_output_file_and_stdout(self):
        import io
        import tempfile
        from unittest.mock import patch

        from keybind_dump.cli import run_cli

        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as f:
            f.write('{"sequence": "C-x C-f", "keymap": "global-map", "command": "find-file"}\n')
            f.write('{"sequence": "C-x C-s", "keymap": "global-map", "command": "save-buffer"}\n')
            in_path = f.name

        out_path = in_path + ".out.json"
        try:
            # Run with file output
            run_cli([in_path, "-f", "json", "-o", out_path])
            self.assertTrue(Path(out_path).exists())
            content = json.loads(Path(out_path).read_text(encoding="utf-8"))
            self.assertIn("C-x C-f", content)

            # Run with stdout output
            mock_stdout = io.StringIO()
            with patch("sys.stdout", mock_stdout):
                run_cli([in_path, "-s", "C-f", "-f", "text"])
            self.assertIn("find-file", mock_stdout.getvalue())
            self.assertNotIn("save-buffer", mock_stdout.getvalue())
        finally:
            Path(in_path).unlink(missing_ok=True)
            Path(out_path).unlink(missing_ok=True)

    def test_dumper_run_dump_and_iter_dump_error(self):
        import subprocess
        from unittest.mock import MagicMock, patch

        from keybind_dump.dumper import iter_dump, run_dump

        # Test run_dump verbose vs non-verbose
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stderr="")
            rc = run_dump(quick=True, verbose=True)
            self.assertEqual(rc, 0)
            mock_run.assert_called_once()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=1, stderr="Error occurred")
            with patch("sys.stderr.write") as mock_stderr:
                rc = run_dump(quick=True, verbose=False)
                self.assertEqual(rc, 1)
                mock_stderr.assert_called_with("Error occurred")

        # Test iter_dump error exit raising RuntimeError
        proc_mock = MagicMock()
        proc_mock.stdout = ["line1\n", "line2\n"]
        proc_mock.stderr = ["Something failed\n"]
        proc_mock.poll.return_value = 1
        proc_mock.wait.return_value = 1

        with (
            patch("subprocess.Popen", return_value=proc_mock),
            patch("sys.stderr.write") as mock_err_write,
        ):
            gen = iter_dump(quick=True)
            with self.assertRaises(RuntimeError):
                list(gen)
            mock_err_write.assert_called_with("Something failed\n")

    def test_dumper_get_elisp_path_not_found(self):
        from unittest.mock import patch

        from keybind_dump.dumper import get_elisp_path

        with patch("pathlib.Path.is_file", return_value=False), self.assertRaises(FileNotFoundError):
            get_elisp_path()


if __name__ == "__main__":
    unittest.main()
