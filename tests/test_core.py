import sys
from pathlib import Path
import unittest

# Ensure src is in sys.path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from keybind_dump.models import KeyBinding, KeybindCollection
from keybind_dump.stats import sequence_duplicate_stats, keymap_duplicate_stats
from keybind_dump.mermaid import generate_mermaid_venn


class TestKeybindModels(unittest.TestCase):
    def setUp(self):
        self.bindings = [
            KeyBinding("C-x C-f", "global-map", "find-file"),
            KeyBinding("C-x C-f", "dired-mode-map", "dired-find-file"),
            KeyBinding("C-x C-s", "global-map", "save-buffer"),
            KeyBinding("q", "dired-mode-map", "quit-window"),
            KeyBinding("q", "help-mode-map", "quit-window"),
            KeyBinding("h", "help-mode-map", "describe-mode"),
            KeyBinding('"', "quote-mode-map", "self-insert-command"),
        ]
        self.coll = KeybindCollection(self.bindings)

    def test_nested_structure(self):
        nested = self.coll.to_nested_dict()
        self.assertIn("C-x C-f", nested)
        self.assertEqual(
            nested["C-x C-f"],
            {"global-map": "find-file", "dired-mode-map": "dired-find-file"},
        )
        self.assertEqual(nested["C-x C-s"], {"global-map": "save-buffer"})

    def test_duplicates(self):
        dups = self.coll.duplicates()
        self.assertEqual(set(dups.keys()), {"C-x C-f", "q"})
        self.assertNotIn("C-x C-s", dups)

    def test_filter(self):
        # By sequence regex
        filtered_seq = self.coll.filter(sequence_pattern=r"^C-x")
        self.assertEqual(set(filtered_seq.to_nested_dict().keys()), {"C-x C-f", "C-x C-s"})

        # By keymap regex
        filtered_km = self.coll.filter(keymap_pattern=r"help")
        self.assertEqual(filtered_km.get_all_keymaps(), ["help-mode-map"])

        # By command regex
        filtered_cmd = self.coll.filter(command_pattern=r"find")
        self.assertEqual(set(filtered_cmd.to_nested_dict().keys()), {"C-x C-f"})

        # Duplicates only
        filtered_dups = self.coll.filter(duplicates_only=True)
        self.assertEqual(set(filtered_dups.to_nested_dict().keys()), {"C-x C-f", "q"})

    def test_search(self):
        res = self.coll.search(sequence="C-x C-s")
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0].command, "save-buffer")

        res_cmd = self.coll.search(command="quit-window")
        self.assertEqual(len(res_cmd), 2)

    def test_stats(self):
        seq_stats = sequence_duplicate_stats(self.coll, min_count=2)
        self.assertEqual(len(seq_stats), 2)
        self.assertEqual(seq_stats[0].count, 2)

        km_stats = keymap_duplicate_stats(self.coll)
        # dired-mode-map has C-x C-f (overlap 1) and q (overlap 1) => score 2
        dired_stat = next(s for s in km_stats if s.keymap == "dired-mode-map")
        self.assertEqual(dired_stat.total_duplicate_score, 2)

    def test_mermaid_generation(self):
        chart = generate_mermaid_venn(self.coll)
        self.assertIn("flowchart TD", chart)
        self.assertIn("subgraph km_global_map", chart)
        self.assertIn("Shared / Intersecting Keybindings", chart)
        self.assertIn("C-x C-f", chart)
        # Quote escaping test
        self.assertIn("&quot;", chart)


if __name__ == "__main__":
    unittest.main()
