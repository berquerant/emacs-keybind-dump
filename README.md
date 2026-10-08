# emacs-keybind-dump

Dump, analyze, filter, and visualize Emacs keybindings across keymaps.

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
- **Mermaid Venn Visualization**:
  - Generates Mermaid flowchart syntax representing keymaps and their shared intersections.

## Setup & Requirements

- Emacs (>= 27.x)
- Python 3.10+
- [mise-en-place](https://mise.jdx.dev/)

```bash
mise run dump       # Dump keybindings to JSONL stdout
mise run test       # Run Python test suite
```

## Usage

### 1. Dump to JSONL

```bash
./bin/dump.sh > keybindings.jsonl
```

### 2. Transform to `{sequence: {keymap: command}}`

```bash
python3 -m keybind_dump transform keybindings.jsonl
```

### 3. Display Duplicates

```bash
python3 -m keybind_dump duplicates keybindings.jsonl
```

### 4. Duplicate Statistics

```bash
# Top duplicate sequences and most overlapping keymaps
python3 -m keybind_dump stats keybindings.jsonl --limit 10
```

### 5. Filter & Search

```bash
# Search by sequence
python3 -m keybind_dump search keybindings.jsonl --sequence "C-x C-f"

# Filter by regex
python3 -m keybind_dump filter keybindings.jsonl --keymap-regex "Buffer-menu" --format json
```

### 6. Mermaid Venn-like Visualization

```bash
python3 -m keybind_dump mermaid keybindings.jsonl \
  --keymap Buffer-menu-mode-map \
  --keymap tabulated-list-mode-map
```
