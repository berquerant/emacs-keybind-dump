# emacs-keybind-dump

Dump, analyze, filter, and search Emacs keybindings across keymaps.

## Features

- **Batch Dump**: Run Emacs in batch mode (`emacs --batch`) to extract all keybindings (`sequence`, `keymap`, `command`) into JSONL.
- **Data Transformation**: Convert flat keybinding stream into `{sequence: {keymap: command}}`.
- **Duplicate Detection**: Identify sequences that conflict or are shared across multiple keymaps.
- **Statistics**:
  - Duplicate frequency count per sequence (sorted descending).
  - Overall duplicate score rankings per keymap.
- **Filter & Search**:
  - Regex filter on sequence, keymap, or command.
  - Exact query on sequence, keymap, or command.
  - Duplicate-only filtering.

## Setup & Requirements

- Emacs (>= 27.x)
- [mise-en-place](https://mise.jdx.dev/) (manages Python 3.14 & [uv](https://docs.astral.sh/uv/))

```bash
mise run dump       # Dump keybindings to JSONL stdout
mise run test       # Run test suite with uv
```

## Usage

### 1. Dump to JSONL

```bash
./bin/dump.sh > keybindings.jsonl
# or via mise
mise run dump > keybindings.jsonl

# Specify custom init directory (loads DIR/init.el)
./bin/dump.sh -d ~/.config/emacs > keybindings.jsonl

# Specify custom init file
./bin/dump.sh -i /path/to/custom-init.el > keybindings.jsonl

# Or via environment variables
EMACS_INIT_DIR=~/.config/emacs ./bin/dump.sh > keybindings.jsonl
```

### 2. Transform to `{sequence: {keymap: command}}`

```bash
./bin/keybind-dump transform keybindings.jsonl
# or via mise
mise run cli -- transform keybindings.jsonl
```

### 3. Display Duplicates

```bash
./bin/keybind-dump duplicates keybindings.jsonl
```

### 4. Duplicate Statistics

```bash
# Top duplicate sequences and most overlapping keymaps
./bin/keybind-dump stats keybindings.jsonl --limit 10
```

### 5. Filter & Search

```bash
# Search by sequence
./bin/keybind-dump search keybindings.jsonl --sequence "C-x C-f"

# Filter by regex
./bin/keybind-dump filter keybindings.jsonl --keymap-regex "Buffer-menu" --format json
```
