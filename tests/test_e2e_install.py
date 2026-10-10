"""End-to-End tests for building and pip-installing emacs-keybind-dump."""

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path


class TestE2EInstallAndRun(unittest.TestCase):
    """Verify wheel build, pip install in clean venv, and CLI execution."""

    tmpdir: tempfile.TemporaryDirectory[str]
    venv_dir: Path
    cli_bin: Path

    @classmethod
    def setUpClass(cls) -> None:
        cls.tmpdir = tempfile.TemporaryDirectory()
        tmp_path = Path(cls.tmpdir.name)
        dist_dir = tmp_path / "dist"
        cls.venv_dir = tmp_path / "venv"

        repo_root = Path(__file__).resolve().parent.parent

        # 1. Build wheel into isolated dist directory
        subprocess.run(
            ["uv", "build", "--wheel", "--out-dir", str(dist_dir)],
            cwd=repo_root,
            check=True,
            capture_output=True,
        )

        wheel_files = list(dist_dir.glob("*.whl"))
        if not wheel_files:
            raise FileNotFoundError(f"No .whl file found in {dist_dir}")
        wheel_file = wheel_files[0]

        # 2. Create clean virtual environment with pip
        subprocess.run(
            ["uv", "venv", "--seed", str(cls.venv_dir)],
            check=True,
            capture_output=True,
        )

        pip_bin = cls.venv_dir / "bin" / "pip"
        cls.cli_bin = cls.venv_dir / "bin" / "keybind-dump"

        # 3. Pip install the built wheel
        subprocess.run(
            [str(pip_bin), "install", str(wheel_file)],
            check=True,
            capture_output=True,
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tmpdir.cleanup()

    def test_cli_help(self) -> None:
        """Verify keybind-dump --help succeeds in installed environment."""
        res = subprocess.run(
            [str(self.cli_bin), "--help"],
            capture_output=True,
            text=True,
            cwd=self.tmpdir.name,  # Run from outside repo root
            check=False,
        )
        self.assertEqual(res.returncode, 0)
        self.assertIn("Dump, filter, analyze, and format Emacs keybindings", res.stdout)

    def test_cli_emacs_dump_with_bundled_elisp(self) -> None:
        """Verify keybind-dump runs batch Emacs using the bundled elisp file."""
        res = subprocess.run(
            [str(self.cli_bin), "-Q", "-f", "jsonl", "--limit", "5"],
            capture_output=True,
            text=True,
            cwd=self.tmpdir.name,  # Run from outside repo root
            check=False,
        )
        self.assertEqual(
            res.returncode,
            0,
            f"keybind-dump failed with stderr:\n{res.stderr}",
        )
        lines = [line.strip() for line in res.stdout.splitlines() if line.strip()]
        self.assertGreaterEqual(
            len(lines),
            1,
            f"Expected at least 1 line. rc={res.returncode}, stdout={res.stdout!r}, stderr={res.stderr!r}",
        )

        # Ensure valid JSON output
        for line in lines:
            data = json.loads(line)
            self.assertIn("sequence", data)
            self.assertIn("keymap", data)
            self.assertIn("command", data)

    def test_cli_file_processing_and_stats(self) -> None:
        """Verify offline file processing and stats work properly."""
        sample_file = Path(self.tmpdir.name) / "sample.jsonl"
        sample_file.write_text(
            '{"sequence": "C-x C-f", "keymap": "global-map", "command": "find-file"}\n'
            '{"sequence": "C-x C-f", "keymap": "dired-mode-map", "command": "dired-find-file"}\n'
            '{"sequence": "q", "keymap": "dired-mode-map", "command": "quit-window"}\n',
            encoding="utf-8",
        )

        res = subprocess.run(
            [str(self.cli_bin), str(sample_file), "--stats", "-f", "json"],
            capture_output=True,
            text=True,
            cwd=self.tmpdir.name,
            check=False,
        )
        self.assertEqual(res.returncode, 0, f"Error:\n{res.stderr}")
        stats = json.loads(res.stdout)
        self.assertIn("summary", stats)
        self.assertEqual(stats["summary"]["total_records"], 3)


if __name__ == "__main__":
    unittest.main()
