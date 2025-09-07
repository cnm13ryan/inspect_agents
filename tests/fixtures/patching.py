from __future__ import annotations

from contextlib import contextmanager
from importlib import import_module
from typing import Any
from unittest.mock import create_autospec, patch


@contextmanager
def patch_use_site(import_path: str, *, new: Any | None = None, autospec: bool = True):
    """Patch an attribute at its use-site import path.

    Purpose: encourage robust patches that survive import refactors and
    catch signature drift when patching callables.

    Behavior:
    - When ``new`` is ``None`` and ``autospec`` is True (default), this behaves
      like ``patch(import_path, autospec=True)`` and yields an autospecced mock.
    - When ``new`` is provided and the original target is callable and
      ``autospec`` is True, the helper wraps ``new`` in a ``create_autospec``
      mock of the original target and forwards via ``side_effect``. This
      preserves the original call signature and raises ``TypeError`` on
      mismatches while still executing ``new`` on valid calls.
    - Otherwise the helper falls back to ``patch(import_path, new=new)``.

    Example
    -------
    >>> from tests.fixtures.patching import patch_use_site
    >>> with patch_use_site('inspect_agents.approval.handoff_exclusive_policy', new=lambda: ['EXCL']):
    ...     pass

    Parameters
    ----------
    import_path: str
        Dotted path to target attribute (e.g., 'pkg.module.attr').
    new: Any | None
        Replacement object or callable. If ``None``, an autospecced mock is used
        when ``autospec`` is True.
    autospec: bool
        Whether to enforce the original target's signature when the target is
        callable. Defaults to True.
    """

    module_path, _, attr = import_path.rpartition(".")
    if not module_path or not attr:
        raise ValueError("import_path must be of the form 'pkg.module.attr'")

    original: Any | None = None
    try:
        mod = import_module(module_path)
        original = getattr(mod, attr)
    except Exception:
        # Defer to unittest.mock.patch to raise a clearer error later
        original = None

    # Case 1: No replacement provided — create an autospecced mock if requested
    if new is None:
        with patch(import_path, autospec=autospec):
            yield
        return

    # Case 2: Replacement provided
    if autospec and callable(original):
        # Build an autospecced callable that forwards to `new` while enforcing
        # the original's call signature.
        proxy = create_autospec(original, spec_set=True)
        proxy.side_effect = new  # type: ignore[assignment]
        with patch(import_path, new=proxy):
            yield
    else:
        # Fallback: simple replacement without autospec
        with patch(import_path, new=new):
            yield
