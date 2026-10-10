# emacs-keybind-dump

Dump, filter, analyze, and format Emacs keybindings across keymaps.

`emacs-keybind-dump` inspects all keybindings active in an Emacs configuration by launching Emacs in batch mode, dumping binding tuples (`sequence`, `keymap`, `command`), and providing a unified CLI for querying, matrix generation, and conflict statistics.

---

## Features

- **Direct Emacs Extraction**:
  - Automatically launches Emacs in batch mode (`-d`, `-i`, or `-Q`) and extracts keybindings in a single command.
  - Automatically respects `$EMACSD` or `$EMACS_INIT_DIR` as the default init directory.
  - Silent by default: Emacs `stderr` noise is suppressed during successful dumps and only displayed if Emacs fails or when `-v, --verbose` is requested.
- **Unified Querying & Filtering**:
  - Filter keybindings by sequence (`-s`), keymap (`-k`), or command (`-c`) using regular expressions.
  - Detect duplicate keybindings (`-D, --duplicates-only`) across multiple keymaps.
- **Flexible Output Formats (`-f, --format`)**:
  - `text`: Human-readable list of bindings (`[sequence] keymap -> command`).
  - `tsv`: Matrix representation with key sequences as rows and keymaps as columns. Missing bindings are filled with a customizable placeholder (default: `None`).
  - `json`: Compact nested mapping (`{"sequence": {"keymap": "command"}}`).
  - `jsonl`: Compact line-delimited stream of binding objects.
- **Duplicate & Conflict Statistics (`--stats`)**:
  - Detailed summary of overlaps and keymap conflicts across configurations.
  - Breakdown by sequence (detecting whether shared keys bind identical commands or trigger conflicting commands).
  - Breakdown by keymap (measuring total, exclusive, shared bindings, conflict rate %, and top overlapping keymaps).
  - Formattable as `text`, `json`, or `tsv`.

---

## Setup & Requirements

- Emacs (>= 27.x)
- Python (>= 3.10) managed via [mise-en-place](https://mise.jdx.dev/) and [uv](https://docs.astral.sh/uv/)

### Installation & Quick Tasks

```bash
# Dump keybindings directly to stdout as JSONL via task runner
mise run dump

# Run test suite
mise run test

# Run linter and type checker
mise run lint
```

---

## Usage

`keybind-dump` functions as a single unified command. If no input file is specified and standard input is interactive, it **automatically dumps keybindings directly from Emacs**.

```bash
keybind-dump [INPUT] [OPTIONS]
```

### 1. Extract Directly from Emacs

```bash
# Dump and display keybindings from default Emacs configuration ($EMACSD or $EMACS_INIT_DIR)
keybind-dump

# Dump Emacs keybindings directly into JSONL
keybind-dump -f jsonl > keybindings.jsonl

# Quick mode (skip user init file, inspect default Emacs bindings)
keybind-dump -Q

# Specify a custom init directory or init file
keybind-dump -d ~/.config/emacs
keybind-dump -i ~/.emacs.d/init.el

# Require specific modes or packages before dumping so their keymaps are loaded
keybind-dump --eval "(require 'org)" --eval "(require 'markdown-mode)"

# Load a custom setup script before dumping (can also register `keybind-dump-before-dump-hook`)
keybind-dump --load setup-modes.el

# Inspect Emacs stderr output (useful for debugging init file warnings)
keybind-dump -v
```

### 2. Filtering & TSV Matrix Generation

`keybind-dump` makes it easy to compare keymaps side-by-side without intermediate files:

```bash
# Export duplicate keybindings into a TSV matrix
keybind-dump -D -f tsv -o duplicates.tsv

# Compare specific keymaps side-by-side as TSV matrix columns
keybind-dump -k global-map -k dired-mode-map -f tsv

# Customize the missing-key placeholder in TSV matrix
keybind-dump -k global-map -k help-map -f tsv --none-value "-"

# Filter by key sequence regex (e.g., keys starting with C-x C-)
keybind-dump -s "^C-x C-"

# Filter by command regex
keybind-dump -c "toggle"
```

#### TSV Matrix Structure
When `-f tsv` is selected, output follows a pivot layout:
| keybind | global-map | dired-mode-map |
| :--- | :--- | :--- |
| `q` | `None` | `quit-window` |
| `C-x C-f` | `find-file` | `None` |

Unmapped slots are populated with the value of `--none-value` (default: `None`).

### 3. Processing Saved Files or Pipelines

You can store keybindings to a JSONL file once and run fast offline queries:

```bash
# Dump once to file
keybind-dump -f jsonl > my-bindings.jsonl

# Query saved file
keybind-dump my-bindings.jsonl -D -f json

# Stream from pipeline
cat my-bindings.jsonl | keybind-dump -s "^C-c"
```

### 4. Duplicate Statistics Summary (`--stats`)

Use `--stats [TARGET]` (where target is `sequence`, `keymap`, or `both`) to analyze keymap overlaps and conflicts:

```bash
# Summary overview including sequence and keymap breakdowns (text format)
keybind-dump --stats

# Sequence duplicates only, showing top 10 most shared sequences
keybind-dump --stats sequence --limit 10

# Keymap duplicates only, showing overlap rates and top conflicting keymaps
keybind-dump --stats keymap --limit 10

# Export structured metrics as compact JSON
keybind-dump --stats -f json

# Export sequence conflict stats as TSV
keybind-dump --stats sequence -f tsv
```

#### Metrics Reported
- **Summary Overview**: Total records, unique sequences, unique keymaps, and shared sequence conflict rate (`shared_sequences / unique_sequences`).
- **Keymap Stats**:
  - `total`: Total bindings assigned in the keymap.
  - `exclusive`: Bindings unique to this keymap.
  - `shared`: Bindings that overlap with at least one other keymap.
  - `conflict_rate`: Percentage of shared bindings (`shared / total`).
  - `score`: Total overlap score ($\sum (\text{overlap count} - 1)$).
  - `top overlaps`: Other keymaps sharing the most keybindings.
- **Sequence Stats**:
  - `count`: Number of keymaps defining this sequence.
  - `status`: `conflict` if different keymaps bind different commands; `same-cmd` if all keymaps bind the exact same command.
  - `commands`: Keymap-to-command mappings.

---

## Command-Line Options Reference

| Option | Group | Description |
| :--- | :--- | :--- |
| `input` | Positional | Input JSONL file or `-` for stdin. If omitted and stdin is a TTY, dumps directly from Emacs. |
| `--dump` | Dump | Force dumping directly from Emacs even when an input argument is supplied. |
| `-d, --init-directory DIR` | Dump | Emacs init directory (loads `DIR/init.el`). Defaults to `$EMACSD` or `$EMACS_INIT_DIR`. |
| `-i, --init-file FILE` | Dump | Explicit Emacs init file to load. Defaults to `$EMACS_INIT_FILE`. |
| `-Q, --quick` | Dump | Run Emacs with `-Q` (quick mode, skipping user configuration). |
| `--emacs-bin BIN` | Dump | Path to `emacs` binary (defaults to `$EMACS_BIN` or `emacs`). |
| `--eval, --eval-before-dump EXPR` | Dump | Evaluate Elisp expression before dumping (e.g. `(require 'org)`). Can be repeated. |
| `--load, --load-before-dump FILE` | Dump | Load Elisp file before dumping. Can be repeated. |
| `-v, --verbose` | Dump | Stream Emacs `stderr` even when execution succeeds. |
| `-D, --duplicates-only` | Filter | Include only key sequences defined in 2 or more keymaps. |
| `-s, --sequence PAT` | Filter | Regular expression filter for key sequences (e.g. `^C-c`). |
| `-k, --keymap PAT` | Filter | Regular expression filter for keymaps. Can be specified multiple times; also defines TSV columns. |
| `-c, --command PAT` | Filter | Regular expression filter for bound command names. |
| `--stats [TARGET]` | Stats | Calculate duplicate statistics (`sequence`, `keymap`, or `both`; default: `both`). |
| `--min-count N` | Stats | Minimum duplicate count threshold for sequence statistics (default: `2`). |
| `--limit N` | Options | Maximum number of records or statistics rows to display. |
| `-f, --format FMT` | Format | Output format: `text` (default), `tsv`, `json`, or `jsonl`. |
| `--none-value STR` | Format | Placeholder for missing bindings in TSV matrix (default: `None`). |
| `-o, --output FILE` | Output | Write output to a file instead of stdout. |

---

## License

MIT
