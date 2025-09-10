#!/usr/bin/env python3
"""Compatibility shim: moved to scripts/scaffold/agent.py"""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

if __name__ == "__main__":
    print(
        "[deprecated] scripts/scaffold_agent.py has moved to scripts/scaffold/agent.py",
        file=sys.stderr,
    )
    target = Path(__file__).with_name("scaffold").joinpath("agent.py")
    sys.exit(runpy.run_path(str(target), run_name="__main__") or 0)
