"""__main__ wrapper for module execution."""

import sys
from pathlib import Path

# Add src to sys.path so it works without pip install
sys.path.insert(0, str(Path(__file__).parent.parent))

from keybind_dump.cli import main

if __name__ == "__main__":
    main()
