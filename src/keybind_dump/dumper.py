"""Emacs batch dump executor."""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path


def get_elisp_path() -> Path:
    """Locate the keybind-dump.el Elisp script.

    Checks:
    1. Relative to repository root (`../../elisp/keybind-dump.el`) for editable/local checkouts.
    2. Within the packaged module directory for installed package distributions.
    """
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
    init_dir: str | None = None,
    init_file: str | None = None,
    quick: bool = False,
    emacs_bin: str | None = None,
    extra_args: Sequence[str] | None = None,
) -> list[str]:
    """Build the command list to run Emacs in batch mode.

    Arguments:
        init_dir: Custom configuration directory. If provided and `init_file` is not set,
            `init_dir/init.el` is loaded automatically if present.
        init_file: Specific init file to load with `-l`.
        quick: If True, or if neither `init_dir` nor `init_file` is specified, runs with `-Q`.
        emacs_bin: Custom Emacs binary executable name or path (defaults to $EMACS_BIN or 'emacs').
        extra_args: Optional list of additional CLI flags passed to Emacs.
    """
    bin_name = emacs_bin or os.environ.get("EMACS_BIN", "emacs")
    cmd = [bin_name, "--batch"]

    # If quick requested, use -Q and skip loading init
    if quick or not init_dir and not init_file:
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
    init_dir: str | None = None,
    init_file: str | None = None,
    quick: bool = False,
    emacs_bin: str | None = None,
    extra_args: Sequence[str] | None = None,
    verbose: bool = False,
    stdout=None,
    stderr=None,
) -> int:
    """Run Emacs in batch mode to dump keybindings as JSONL.

    When `verbose` is False, Emacs stderr is captured silently and only
    flushed to `sys.stderr` if the process exits with a non-zero returncode.
    """
    cmd = build_emacs_cmd(
        init_dir=init_dir,
        init_file=init_file,
        quick=quick,
        emacs_bin=emacs_bin,
        extra_args=extra_args,
    )
    if verbose:
        proc = subprocess.run(
            cmd, stdout=stdout or sys.stdout, stderr=stderr or sys.stderr, check=False
        )
        return proc.returncode

    proc = subprocess.run(
        cmd, stdout=stdout or sys.stdout, stderr=subprocess.PIPE, text=True, check=False
    )
    if proc.returncode != 0 and proc.stderr:
        sys.stderr.write(proc.stderr)
    return proc.returncode


def iter_dump(
    init_dir: str | None = None,
    init_file: str | None = None,
    quick: bool = False,
    emacs_bin: str | None = None,
    extra_args: Sequence[str] | None = None,
    verbose: bool = False,
):
    """Run Emacs in batch mode and yield dumped JSON Lines incrementally.

    Streams output directly from the child process stdout to avoid buffering
    large keybinding datasets in memory simultaneously.

    Stderr Handling:
    - By default (`verbose=False`), a background daemon thread reads and buffers
      stderr chunks without blocking stdout iteration.
    - If Emacs terminates successfully (exit code 0), stderr buffer is discarded.
    - If Emacs fails (non-zero exit code), buffered stderr is written to `sys.stderr`
      and a RuntimeError is raised.
    - If `verbose=True`, stderr is passed directly through to `sys.stderr`.
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
            err_chunks.extend(proc.stderr)

    reader_thread = None
    if not verbose:
        reader_thread = threading.Thread(target=_read_stderr, daemon=True)
        reader_thread.start()

    try:
        if proc.stdout:
            yield from proc.stdout
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()
        if reader_thread and reader_thread.is_alive():
            reader_thread.join(timeout=1)

    rc = proc.wait()
    if rc != 0:
        if err_chunks:
            sys.stderr.write("".join(err_chunks))
        raise RuntimeError(f"Emacs batch dump exited with error code {rc}")
