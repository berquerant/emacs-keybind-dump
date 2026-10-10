# emacs-keybind-dump

Dump, analyze, filter, and format Emacs keybindings across keymaps.

## Features

- **Batch Dump**: Run Emacs in batch mode (`emacs --batch`) to extract all keybindings (`sequence`, `keymap`, `command`) into JSONL.
- **Unified Querying & Filtering**:
  - Filter by sequence, keymap, or command with regex patterns.
  - Duplicate-only detection (`-d, --duplicates-only`).
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

### 1. Dump Keybindings from Emacs (`keybind-dump dump`)

```bash
# Dump keybindings to stdout using default init dir ($EMACSD or $EMACS_INIT_DIR)
./bin/keybind-dump dump > keybindings.jsonl
# or via mise
mise run dump > keybindings.jsonl

# Specify custom init directory (loads DIR/init.el)
./bin/keybind-dump dump -d ~/.config/emacs > keybindings.jsonl

# Specify custom init file
./bin/keybind-dump dump -i /path/to/custom-init.el > keybindings.jsonl

# Quick mode (skip loading user init, loads only default Emacs keybindings)
./bin/keybind-dump dump -Q > keybindings.jsonl

# Pipe directly into filter/format without temporary file!
./bin/keybind-dump dump | ./bin/keybind-dump -d -f tsv
```

### 2. View and Filter Keybindings

```bash
# Display all keybindings (text format)
./bin/keybind-dump keybindings.jsonl

# Filter by sequence regex
./bin/keybind-dump keybindings.jsonl -s "^C-x C-f"

# Filter by keymap and command regex
./bin/keybind-dump keybindings.jsonl -k "Buffer-menu" -c "toggle"

# Filter duplicate keybindings (conflicts across >= 2 keymaps)
./bin/keybind-dump keybindings.jsonl --duplicates-only
```

### 3. Output Formats (`-f, --format`)

```bash
# TSV Matrix: Keybindings as rows, keymaps as columns
./bin/keybind-dump keybindings.jsonl -f tsv

# TSV Matrix specifying specific keymaps as columns
./bin/keybind-dump keybindings.jsonl -k global-map -k dired-mode-map -f tsv -o matrix.tsv

# Nested JSON: {sequence: {keymap: command}}
./bin/keybind-dump keybindings.jsonl -f json

# Flat JSONL stream
./bin/keybind-dump keybindings.jsonl -f jsonl
```

### 4. Duplicate Statistics Summary (`--stats`)

Use `--stats` to compute summary metrics across keybindings, and combine with `-f, --format` to choose the output representation:

```bash
# Text summary (default: sequence duplicate counts and keymap scores)
./bin/keybind-dump keybindings.jsonl --stats

# Sequence duplicate stats only
./bin/keybind-dump keybindings.jsonl --stats sequence --limit 10

# Structured JSON summary
./bin/keybind-dump keybindings.jsonl --stats -f json

# TSV summary
./bin/keybind-dump keybindings.jsonl --stats sequence -f tsv
```
