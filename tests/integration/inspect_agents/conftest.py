"""Integration test bootstrap.

Behavior:
- Ensure repo `src/` is importable and prefer the installed `inspect_ai`.
- Environment hardening (offline + tool disables) now lives in `tests/conftest.py`
  as a root autouse fixture (`_default_env_guard`). This file keeps only
  integration-specific bootstrap concerns.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
