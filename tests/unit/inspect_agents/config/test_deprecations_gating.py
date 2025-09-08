import warnings

import pytest


def test_aliases_emit_no_warning_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    from inspect_agents import filters as flt
    from inspect_agents import fs

    monkeypatch.delenv("INSPECT_SHOW_DEPRECATIONS", raising=False)

    with warnings.catch_warnings(record=True) as rec:
        warnings.simplefilter("always")
        _ = fs._fs_mode()
        _ = flt._truthy("1")
    assert not any(w.category is DeprecationWarning for w in rec)


def test_aliases_warn_once_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    from importlib import reload

    import inspect_agents.filters as flt
    import inspect_agents.fs as fs

    monkeypatch.setenv("INSPECT_SHOW_DEPRECATIONS", "1")
    # Reload modules to pick up env at import-time evaluated flags
    fs = reload(fs)
    flt = reload(flt)

    with warnings.catch_warnings(record=True) as rec:
        warnings.simplefilter("always")
        _ = fs._fs_mode()
        _ = fs._fs_mode()
        _ = flt._truthy("1")
        _ = flt._truthy("1")
    dep_warnings = [w for w in rec if w.category is DeprecationWarning]
    # Expect exactly one per alias despite multiple calls
    assert any("_fs_mode" in str(w.message) for w in dep_warnings)
    assert any("_truthy" in str(w.message) for w in dep_warnings)
