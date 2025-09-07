# test(tests): guard against legacy test paths

from __future__ import annotations

import os
from pathlib import Path

# Legacy roots that should remain empty of code going forward.
# Note: historically, tests lived under these roots. This repository now
# hosts first-class suites under "tests/inspect_agents/**" (see docs), so we
# no longer treat that path as legacy. Keep the other legacy roots guarded.
LEGACY_ROOTS = [
    Path("tests/tests"),
    Path("tests/research"),
    Path("tests/examples"),
]

# Ignore caches and hidden files/folders; compiled artifacts are okay to ignore.
IGNORED_DIRS = {"__pycache__"}
IGNORED_FILENAMES = {".DS_Store"}


def _ignored_file(path: Path) -> bool:
    name = path.name
    if name.startswith("."):
        return True
    if name in IGNORED_FILENAMES:
        return True
    if path.suffix == ".pyc":
        return True
    return False


def test_no_legacy_tests_present() -> None:
    """
    Fails if any new Python tests (or any non-ignored files) appear under
    legacy test roots. Directories are allowed to exist but must be effectively
    empty (only caches/hidden files allowed).
    """

    offenders: list[str] = []

    for root in LEGACY_ROOTS:
        if not root.exists():
            continue

        for dirpath, dirnames, filenames in os.walk(root):
            # Skip ignored directories (prevents descending into __pycache__ etc.)
            dirnames[:] = [d for d in dirnames if d not in IGNORED_DIRS and not d.startswith(".")]

            # Flag any non-ignored files (and all .py files) as violations
            for fname in filenames:
                fpath = Path(dirpath) / fname
                if _ignored_file(fpath):
                    continue
                if fpath.suffix == ".py" or not _ignored_file(fpath):
                    offenders.append(fpath.as_posix())

    assert not offenders, (
        "Legacy test files detected under deprecated roots.\n"
        "Move tests to 'tests/unit/**' or 'tests/integration/**'.\n"
        "Offending paths:\n  - " + "\n  - ".join(sorted(offenders))
    )
