#!/usr/bin/env python3
"""Compatibility shim: moved to scripts/docs/gen-env-docs.py"""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

if __name__ == "__main__":
    print(
        "[deprecated] scripts/gen_env_docs.py has moved to scripts/docs/gen-env-docs.py",
        file=sys.stderr,
    )
    target = Path(__file__).with_name("docs").joinpath("gen-env-docs.py")
    sys.exit(runpy.run_path(str(target), run_name="__main__") or 0)
