"""Emacs batch dump executor."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Sequence


def get_elisp_path() -> Path:
    """Locate the keybind-dump.el file."""
    # 1. Check relative to repo root (src/keybind_dump/../..)
    repo_root = Path(__file__).resolve().parent.parent.parent
    elisp_in_repo = repo_root / "elisp" / "keybind-dump.el"
    if elisp_in_repo.is_file():
        return elisp_in_repo

    # 2. Check package data directory if installed
    pkg_dir = Path(__file__).resolve().parent / "elisp" / "keybind-dump.el"
    if pkg_dir.is_file():
        return pkg_dir

    raise FileNotFoundError(
        f"Could not find keybind-dump.el in {elisp_in_repo} or {pkg_dir}"
    )


def build_emacs_cmd(
    init_dir: Optional[str] = None,
    init_file: Optional[str] = None,
    quick: bool = False,
    emacs_bin: Optional[str] = None,
    extra_args: Optional[Sequence[str]] = None,
) -> list[str]:
    """Build the command list to run emacs in batch mode."""
    bin_name = emacs_bin or os.environ.get("EMACS_BIN", "emacs")
    cmd = [bin_name, "--batch"]

    # If quick requested, use -Q and skip loading init
    if quick:
        cmd.append("-Q")
    elif not init_dir and not init_file:
        cmd.append("-Q")
    else:
        if init_dir:
            abs_dir = os.path.abspath(os.path.expanduser(init_dir))
            cmd.extend(["--init-directory", abs_dir])
            if not init_file:
                candidate = os.path.join(abs_dir, "init.el")
                if os.path.isfile(candidate):
                    init_file = candidate

        if init_file:
            abs_file = os.path.abspath(os.path.expanduser(init_file))
            cmd.extend(["-l", abs_file])

    if extra_args:
        cmd.extend(extra_args)

    elisp_file = get_elisp_path()
    cmd.extend(["-l", str(elisp_file), "-f", "keybind-dump-jsonl"])
    return cmd


def run_dump(
    init_dir: Optional[str] = None,
    init_file: Optional[str] = None,
    quick: bool = False,
    emacs_bin: Optional[str] = None,
    extra_args: Optional[Sequence[str]] = None,
    verbose: bool = False,
    stdout=None,
    stderr=None,
) -> int:
    """Run emacs in batch mode to dump keybindings as JSONL."""
    cmd = build_emacs_cmd(
        init_dir=init_dir,
        init_file=init_file,
        quick=quick,
        emacs_bin=emacs_bin,
        extra_args=extra_args,
    )
    if verbose:
        proc = subprocess.run(cmd, stdout=stdout or sys.stdout, stderr=stderr or sys.stderr)
        return proc.returncode

    proc = subprocess.run(cmd, stdout=stdout or sys.stdout, stderr=subprocess.PIPE, text=True)
    if proc.returncode != 0 and proc.stderr:
        sys.stderr.write(proc.stderr)
    return proc.returncode


def iter_dump(
    init_dir: Optional[str] = None,
    init_file: Optional[str] = None,
    quick: bool = False,
    emacs_bin: Optional[str] = None,
    extra_args: Optional[Sequence[str]] = None,
    verbose: bool = False,
):
    """Run emacs in batch mode and yield dumped JSON Lines directly.

    Normally suppresses Emacs stderr unless an error occurs (non-zero exit code)
    or verbose=True is specified.
    """
    import threading

    cmd = build_emacs_cmd(
        init_dir=init_dir,
        init_file=init_file,
        quick=quick,
        emacs_bin=emacs_bin,
        extra_args=extra_args,
    )
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=sys.stderr if verbose else subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )

    err_chunks: list[str] = []

    def _read_stderr():
        if proc.stderr:
            for chunk in proc.stderr:
                err_chunks.append(chunk)

    reader_thread = None
    if not verbose:
        reader_thread = threading.Thread(target=_read_stderr, daemon=True)
        reader_thread.start()

    if proc.stdout:
        for line in proc.stdout:
            yield line

    if reader_thread:
        reader_thread.join()

    rc = proc.wait()
    if rc != 0:
        if err_chunks:
            sys.stderr.write("".join(err_chunks))
        raise RuntimeError(f"Emacs batch dump exited with error code {rc}")
