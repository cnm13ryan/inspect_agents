#!/usr/bin/env python3
"""Compatibility shim: moved to scripts/eval/read-log-eval.py"""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

if __name__ == "__main__":
    print(
        "[deprecated] scripts/read_log_eval.py has moved to scripts/eval/read-log-eval.py",
        file=sys.stderr,
    )
    target = Path(__file__).with_name("eval").joinpath("read-log-eval.py")
    sys.exit(runpy.run_path(str(target), run_name="__main__") or 0)
