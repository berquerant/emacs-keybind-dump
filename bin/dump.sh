#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
ELISP_FILE="${REPO_ROOT}/elisp/keybind-dump.el"

EMACS_BIN="${EMACS_BIN:-emacs}"

init_dir="${EMACS_INIT_DIR:-}"
init_file="${EMACS_INIT_FILE:-}"
quick=false
extra_args=()

show_help() {
  cat << 'EOF'
Usage: dump.sh [OPTIONS] [-- [EMACS_ARGS...]]

Dump Emacs keybindings to JSONL.

Options:
  -d, --init-directory DIR   Set Emacs init directory and load DIR/init.el
  -i, --init-file FILE       Load specified init file
  -Q, --quick                Run without loading any user init (default when no init is specified)
  -h, --help                 Show this help message

Environment Variables:
  EMACS_INIT_DIR             Default init directory
  EMACS_INIT_FILE            Default init file
  EMACS_BIN                  Path to emacs executable (default: emacs)
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -d|--init-directory)
      init_dir="$2"
      shift 2
      ;;
    -i|--init-file)
      init_file="$2"
      shift 2
      ;;
    -Q|--quick)
      quick=true
      shift
      ;;
    -h|--help)
      show_help
      exit 0
      ;;
    --)
      shift
      extra_args+=("$@")
      break
      ;;
    *)
      extra_args+=("$1")
      shift
      ;;
  esac
done

emacs_cmd=("$EMACS_BIN" --batch)

# If neither init_dir nor init_file is set, or if quick is explicitly requested, use -Q
if [[ "$quick" == true ]] || [[ -z "$init_dir" && -z "$init_file" ]]; then
  emacs_cmd+=(-Q)
fi

if [[ -n "$init_dir" ]]; then
  # Resolve to absolute path if directory exists
  if [[ -d "$init_dir" ]]; then
    init_dir="$(cd "$init_dir" && pwd)"
  fi
  emacs_cmd+=(--init-directory "$init_dir")
  # If init_file is not explicitly given, try loading $init_dir/init.el
  if [[ -z "$init_file" && -f "${init_dir}/init.el" ]]; then
    init_file="${init_dir}/init.el"
  fi
fi

if [[ -n "$init_file" ]]; then
  emacs_cmd+=(-l "$init_file")
fi

if [[ ${#extra_args[@]} -gt 0 ]]; then
  emacs_cmd+=("${extra_args[@]}")
fi

emacs_cmd+=(-l "${ELISP_FILE}" -f keybind-dump-jsonl)

exec "${emacs_cmd[@]}"
