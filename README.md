# emacs-keybind-dump

Dump, filter, analyze, and format Emacs keybindings across keymaps.

## Features

- **Direct Emacs Extraction**: Extracts all keybindings (`sequence`, `keymap`, `command`) directly from Emacs (using `$EMACSD` by default) without intermediate steps.
- **Unified Querying & Filtering**:
  - Filter by sequence, keymap, or command with regex patterns.
  - Duplicate-only detection (`-D, --duplicates-only`).
- **Flexible Output Formats (`-f, --format`)**:
  - `text`: Human-readable list of bindings.
  - `tsv`: Matrix representation of keybindings vs keymaps with assigned commands (or `None`).
  - `json`: Nested `{sequence: {keymap: command}}` mapping.
  - `jsonl`: Flat JSON Lines stream.
- **Duplicate Statistics Summary (`--stats`)**:
  - Sequence duplicate count and keymap duplicate scores.
  - Formattable as `text`, `json`, or `tsv`.

## Setup & Requirements

- Emacs (>= 27.x)
- [mise-en-place](https://mise.jdx.dev/) (manages Python 3.14 & [uv](https://docs.astral.sh/uv/))

```bash
mise run dump       # Dump keybindings to JSONL stdout
mise run test       # Run test suite with uv
```

## Usage

`keybind-dump` is a single unified command. If an input file is not given, it **automatically dumps keybindings directly from Emacs** (using `$EMACSD` or `$EMACS_INIT_DIR` by default).

### 1. Extract and View Keybindings Directly from Emacs

```bash
# Dump and display all keybindings from Emacs ($EMACSD)
keybind-dump

# Dump Emacs keybindings directly into JSONL
keybind-dump -f jsonl > keybindings.jsonl
# or via mise
mise run dump > keybindings.jsonl

# Quick mode (skip user init, extract only default Emacs bindings)
keybind-dump -Q

# Specify custom init directory or init file
keybind-dump -d ~/.config/emacs
keybind-dump -i /path/to/custom-init.el
```

### 2. Direct Emacs Extraction with Filters & Formats (One-liner!)

No temporary files or pipelines needed:

```bash
# Filter duplicate keybindings directly from Emacs as TSV matrix
keybind-dump -D -f tsv -o duplicates.tsv

# Extract specific keymaps as columns in TSV
keybind-dump -k global-map -k dired-mode-map -f tsv

# Find bindings by sequence regex directly from Emacs
keybind-dump -s "^C-x C-f"

# Filter by command regex
keybind-dump -c "toggle"
```

### 3. Processing Saved JSONL Files or Standard Input

You can also pass a previously dumped JSONL file or pipe:

```bash
# Analyze a saved JSONL file
keybind-dump keybindings.jsonl -D -f json

# Read from stdin
cat keybindings.jsonl | keybind-dump -s "^C-c"
```

### 4. Duplicate Statistics Summary (`--stats`)

Use `--stats` to compute summary metrics across keybindings, and combine with `-f, --format` to choose the output representation:

- **Overall Overview**: Total records, unique sequences, unique keymaps, and shared sequence conflict rate.
- **Keymap Stats**: Total bindings, exclusive (unique) bindings, shared bindings, conflict rate (%), conflict score, and top overlapping keymaps.
- **Sequence Stats**: Overlap frequency, conflict status (`conflict` when commands differ across keymaps vs `same-cmd`), and keymap-to-command mappings.

```bash
# Summary of all duplicates directly from Emacs (text format)
keybind-dump --stats

# Sequence duplicate stats only (top 10)
keybind-dump --stats sequence --limit 10

# Keymap duplicate stats only
keybind-dump --stats keymap --limit 10

# Structured JSON summary
keybind-dump --stats -f json

# TSV summary
keybind-dump --stats sequence -f tsv
```
