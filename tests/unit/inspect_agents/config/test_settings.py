import pytest

from inspect_agents.settings import (
    default_tool_timeout,
    float_env,
    int_env,
    max_tool_output_env,
    str_env,
    truthy,
    typed_results_enabled,
)


def test_truthy_values() -> None:
    assert truthy("1")
    assert truthy("true")
    assert truthy("YES")
    assert truthy("On")
    assert not truthy(None)
    assert not truthy("")
    assert not truthy("0")
    assert not truthy("nope")


def test_int_env_min_max(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("X_INT", "5")
    assert int_env("X_INT", 3, minimum=10) == 10
    assert int_env("X_INT", 3, maximum=4) == 4
    # invalid -> default
    monkeypatch.setenv("X_INT", "abc")
    assert int_env("X_INT", 7) == 7
    # unset -> default
    monkeypatch.delenv("X_INT", raising=False)
    assert int_env("X_INT", 9) == 9


def test_float_env_invalid_and_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("X_FLOAT", "3.5")
    assert float_env("X_FLOAT", 1.0) == pytest.approx(3.5)
    monkeypatch.setenv("X_FLOAT", "oops")
    assert float_env("X_FLOAT", 2.25) == pytest.approx(2.25)
    monkeypatch.delenv("X_FLOAT", raising=False)
    assert float_env("X_FLOAT", 4.0) == pytest.approx(4.0)


def test_str_env_empty_vs_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    # unset -> default
    monkeypatch.delenv("X_STR", raising=False)
    assert str_env("X_STR", "def") == "def"
    # empty is preserved
    monkeypatch.setenv("X_STR", "")
    assert str_env("X_STR", "def") == ""
    monkeypatch.setenv("X_STR", "abc")
    assert str_env("X_STR", None) == "abc"


def test_typed_results_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("INSPECT_AGENTS_TYPED_RESULTS", raising=False)
    assert typed_results_enabled() is False
    monkeypatch.setenv("INSPECT_AGENTS_TYPED_RESULTS", "1")
    assert typed_results_enabled() is True
    monkeypatch.setenv("INSPECT_AGENTS_TYPED_RESULTS", "no")
    assert typed_results_enabled() is False


def test_default_tool_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("INSPECT_AGENTS_TOOL_TIMEOUT", raising=False)
    assert default_tool_timeout() == pytest.approx(15.0)
    monkeypatch.setenv("INSPECT_AGENTS_TOOL_TIMEOUT", "2.5")
    assert default_tool_timeout() == pytest.approx(2.5)
    monkeypatch.setenv("INSPECT_AGENTS_TOOL_TIMEOUT", "bad")
    assert default_tool_timeout() == pytest.approx(15.0)


def test_max_tool_output_env_accessor(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("INSPECT_MAX_TOOL_OUTPUT", raising=False)
    assert max_tool_output_env() is None
    # invalid -> None
    monkeypatch.setenv("INSPECT_MAX_TOOL_OUTPUT", "not-a-number")
    assert max_tool_output_env() is None
    # negative -> None
    monkeypatch.setenv("INSPECT_MAX_TOOL_OUTPUT", "-1")
    assert max_tool_output_env() is None
    # zero allowed
    monkeypatch.setenv("INSPECT_MAX_TOOL_OUTPUT", "0")
    assert max_tool_output_env() == 0
    # positive
    monkeypatch.setenv("INSPECT_MAX_TOOL_OUTPUT", "8192")
    assert max_tool_output_env() == 8192
