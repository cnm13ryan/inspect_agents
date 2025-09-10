#!/usr/bin/env python3
"""Compatibility shim: moved to examples/inspect/quickstart_toy.py"""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

if __name__ == "__main__":
    print(
        "[deprecated] scripts/quickstart_toy.py has moved to examples/inspect/quickstart_toy.py",
        file=sys.stderr,
    )
    target = Path(__file__).resolve().parents[1] / "examples" / "inspect" / "quickstart_toy.py"
    sys.exit(runpy.run_path(str(target), run_name="__main__") or 0)
