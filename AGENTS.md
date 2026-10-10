# AGENTS.md

## Keeping This File Up to Date

When you make structural changes to the project (adding/removing modules, commands, options, or conventions), **update this file** so it accurately reflects the current state of the codebase. Treat AGENTS.md as living documentation: if the code contradicts what is written here, fix AGENTS.md.

---

## Project Overview

**emacs-keybind-dump** is a CLI tool and Python library designed to inspect, dump, analyze, filter, and format keybindings across Emacs keymaps.

It launches Emacs in batch mode (`--batch`), evaluates keybindings via an embedded Elisp script (`keybind-dump.el`), and extracts binding tuples (`sequence`, `keymap`, `command`). It provides powerful query filtering, duplicate detection, TSV matrix pivot generation, and keymap conflict statistics.

---

## Repository Layout

```
emacs-keybind-dump/
├── .github/
│   ├── dependabot.yml       # Dependabot configuration (github-actions, uv)
│   └── workflows/
│       └── ci.yml           # GitHub Actions CI workflow (lint & test jobs)
├── bin/
│   └── keybind-dump         # Standalone shell wrapper script
├── scripts/
│   └── release.py           # Automated SemVer release script (bump, uv lock, commit, tag, push)
├── src/
│   └── keybind_dump/        # Main Python package
│       ├── __init__.py      # Package metadata and public re-exports
│       ├── __main__.py      # Entry point for `python -m keybind_dump`
│       ├── cli.py           # argparse CLI definition, stdin/dump dispatch, main()
│       ├── dumper.py        # Subprocess caller for Emacs batch execution & Elisp path resolution
│       ├── formatters.py    # Output formatters (text, tsv matrix, json, jsonl, stats)
│       ├── models.py        # Keybind, KeybindCollection data models & filtering logic
│       ├── stats.py         # Duplicate and conflict statistics calculation logic
│       └── elisp/           # Bundled Elisp package data
│           └── keybind-dump.el # Emacs Lisp script traversing current keymaps
├── tests/
│   ├── test_core.py         # Unit tests (models, formatters, stats, CLI argument handling)
│   └── test_e2e_install.py  # E2E tests (wheel build, clean venv pip install, and CLI execution)
├── mise.toml                # mise task runner & tool configuration (python, uv)
├── pyproject.toml           # Project metadata, Hatch build configuration, dependencies, mypy
├── uv.lock                  # uv lockfile for reproducible dependency management
└── README.md                # User-facing documentation
```

---

## Development Setup

Requires **Python ≥ 3.10** (default 3.14), **Emacs ≥ 27.x**, and [mise-en-place](https://mise.jdx.dev/) with [uv](https://docs.astral.sh/uv/).

```shell
# Install tools and dependencies
mise install
uv sync --dev
```

---

## Task Runner Commands (`mise`)

| Task | Command | Description |
|---|---|---|
| `mise run dump` | `uv run keybind-dump -f jsonl` | Dump active Emacs keybindings to JSONL |
| `mise run test` | `uv run python -m unittest discover -s tests` | Run all tests (unit and E2E) |
| `mise run test:unit` | `uv run python -m unittest tests/test_core.py` | Run fast unit tests |
| `mise run test:e2e` | `uv run python -m unittest tests/test_e2e_install.py` | Run wheel build & pip install E2E test |
| `mise run lint:ruff` | `uv run ruff check src tests scripts` | Run ruff linter |
| `mise run lint:mypy` | `uv run mypy src tests scripts` | Run mypy type checker |
| `mise run lint` | Depends: `lint:ruff`, `lint:mypy` | Run all linters and type checkers |
| `mise run ci` | Depends: `lint`, `test` | Run all lint and test checks |
| `mise run release <VER>` | `uv run python scripts/release.py <VER>` | Run release script (tests, bump, tag, push) |

---

## Architecture & Core Modules

### 1. Direct Emacs Extraction (`dumper.py` & `keybind-dump.el`)
- **Package data bundling**: `keybind-dump.el` lives under `src/keybind_dump/elisp/` and is bundled inside wheels and source distributions. `get_elisp_path()` locates this script at runtime.
- **Batch execution**: `iter_dump()` launches `emacs --batch` with `-l keybind-dump.el` and yields JSON Lines emitted by Emacs on `stdout`.
- **Custom environment**: Supports `--init-directory`, `--init-file`, `--quick` (`-Q`), `--eval-before-dump` (`(require '...)`), and `--load-before-dump` hooks.

### 2. Models & Collections (`models.py`)
- `Keybind`: Immutable dataclass representing a binding (`sequence`, `keymap`, `command`).
- `KeybindCollection`: Container with filtering capabilities by:
  - Sequence regex (`sequence_pattern`)
  - Keymap regex (`keymap_pattern`)
  - Command regex (`command_pattern`)
  - Duplicate-only mode (`duplicates_only`)

### 3. Formatters (`formatters.py`)
- `text`: Human-readable sequence listing.
- `tsv`: Matrix representation with key sequences as rows, matched keymaps as columns, and `--none-value` for unmapped bindings.
- `json`: Nested mapping `{"<sequence>": {"<keymap>": "<command>"}}`.
- `jsonl`: Line-delimited stream of JSON objects.
- `format_stats()`: Formatted report of sequence and keymap collision metrics.

### 4. Duplicate & Conflict Statistics (`stats.py`)
- Measures conflict rates across keymaps.
- Categorizes collisions into `conflict` (conflicting commands) vs `same-cmd` (same command bound in multiple keymaps).

### 5. CLI Dispatch (`cli.py`)
- If an input file is provided, reads from that file or stdin.
- If input is omitted or `-Q`/`--dump` flags are given, automatically invokes direct Emacs extraction.

---

## Release Process

Release is automated using [`scripts/release.py`](scripts/release.py):

```shell
mise run release 0.2.0
# or with dry-run
mise run release --dry-run 0.2.0
```

Steps executed:
1. Validates SemVer format.
2. Checks git working tree is clean.
3. Checks tag collision against local and remote tags.
4. Executes full test suite (`test:unit` and `test:e2e`).
5. Bumps version in `pyproject.toml`.
6. Runs `uv lock` to update `uv.lock`.
7. Creates commit `release: v<version>` and annotated tag `v<version>`.
8. Pushes branch and tag to `origin` (if remote is configured).

---

## CI / CD Workflows

Defined in [`.github/workflows/ci.yml`](.github/workflows/ci.yml):
- **Lint job**: Runs `jdx/mise-action` and `mise run lint`.
- **Test job**: Sets up Emacs 30.1 via `purcell/setup-emacs`, runs `jdx/mise-action`, and executes `mise run test` (including E2E pip installation tests).
- **Dependabot**: Automatically checks `github-actions` and `uv` dependencies on a weekly basis.
