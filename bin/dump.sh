#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
ELISP_FILE="${REPO_ROOT}/elisp/keybind-dump.el"

exec emacs --batch -Q -l "${ELISP_FILE}" -f keybind-dump-jsonl
