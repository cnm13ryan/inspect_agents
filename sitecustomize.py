"""Test-time bootstrap shims.

Pytest imports this repository as the working directory is on sys.path. Python
will import `sitecustomize` (if present) after the standard `site` module. We
use this hook to provide minimal compatibility shims so that vendored Inspect-AI
imports succeed consistently across environments.
"""

from __future__ import annotations

import importlib.abc as _abc
import importlib.machinery as _machinery
import importlib.util
import sys
from types import ModuleType


# Ensure vendored Inspect-AI loads cleanly with approvals shim, and make the
# commonly patched subpackage `inspect_ai.model` available on the parent.
class _InspectAIModelAttrFinder(_abc.MetaPathFinder):
    def find_spec(self, fullname, path, target=None):  # type: ignore[override]
        # Wrap the root package and selected subpackages to ensure parent has
        # a `model` attribute regardless of package init behavior.
        wrap = fullname == "inspect_ai" or fullname.startswith("inspect_ai.tool")
        if not wrap:
            return None
        spec = _machinery.PathFinder.find_spec(fullname, path)
        if spec and spec.loader:
            spec.loader = _InspectAIModelAttrLoader(spec.loader)  # type: ignore[assignment]
        return spec


class _InspectAIModelAttrLoader(_abc.Loader):
    def __init__(self, inner: _abc.Loader):
        self._inner = inner

    def create_module(self, spec):  # pragma: no cover - passthrough
        if hasattr(self._inner, "create_module"):
            return getattr(self._inner, "create_module")(spec)  # type: ignore[misc]
        return None

    def exec_module(self, module):  # pragma: no cover - simple wrapper
        self._inner.exec_module(module)
        try:
            import importlib as _importlib

            # Ensure parent package has `model` attribute
            parent = module
            if module.__name__ != "inspect_ai":
                import sys as _sys

                parent = _sys.modules.get("inspect_ai", parent)
            sub = _importlib.import_module("inspect_ai.model")
            if getattr(parent, "model", None) is None:
                setattr(parent, "model", sub)
        except Exception:
            pass


try:
    # Prepend finder so it wraps the initial import of inspect_ai
    sys.meta_path.insert(0, _InspectAIModelAttrFinder())
except Exception:
    pass


def _ensure_inspect_ai_approval_apply() -> None:
    """Install a lightweight inspect_ai.approval._apply if missing.

    Newer Inspect-AI imports `have_tool_approval` and `init_tool_approval` at
    import time. Some environments run against a subset/stubbed approval module.
    This shim prevents ImportError during test collection without altering
    runtime behavior when a real module exists.
    """

    try:
        spec = importlib.util.find_spec("inspect_ai.approval._apply")
        if spec is not None:
            return  # real implementation available
    except Exception:
        # Fall through to install stub
        pass

    # Ensure package parent exists to host the submodule
    pkg_name = "inspect_ai.approval"
    if pkg_name not in sys.modules:
        pkg = ModuleType(pkg_name)
        sys.modules[pkg_name] = pkg

    # Install stub submodule
    mod = ModuleType("inspect_ai.approval._apply")
    _policies: list[object] | None = None

    def init_tool_approval(policies):  # noqa: D401
        """Initialize tool approval policies (shim)."""
        nonlocal _policies
        _policies = list(policies) if policies else []

    def have_tool_approval():  # noqa: D401
        """Return True if any approval policies are active (shim)."""
        return bool(_policies)

    async def apply_tool_approval(message, call, viewer, history):  # noqa: D401
        """Approve by default (shim)."""

        class _Approval:
            decision = "approve"
            modified = None
            explanation = None

        return True, _Approval()

    mod.init_tool_approval = init_tool_approval  # type: ignore[attr-defined]
    mod.have_tool_approval = have_tool_approval  # type: ignore[attr-defined]
    mod.apply_tool_approval = apply_tool_approval  # type: ignore[attr-defined]
    sys.modules["inspect_ai.approval._apply"] = mod


try:
    _ensure_inspect_ai_approval_apply()
except Exception:
    # Never block startup on optional shim
    pass

# Import inspect_ai and its model submodule early so attribute-based patch
# targets resolve reliably (some versions do not attach subpackages by default).
try:  # pragma: no cover - environment bootstrap
    import importlib as _importlib

    _ia = _importlib.import_module("inspect_ai")
    _importlib.import_module("inspect_ai.model")
    if getattr(_ia, "model", None) is None and "inspect_ai.model" in sys.modules:
        setattr(_ia, "model", sys.modules["inspect_ai.model"])
except Exception:
    pass
