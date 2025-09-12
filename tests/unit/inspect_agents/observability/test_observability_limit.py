import sys
import types


def _install_generate_config_stub(monkeypatch, max_tool_output):
    """Install a minimal stub for inspect_ai.model._generate_config.

    Provides active_generate_config() returning an object with attribute
    max_tool_output set to the provided value.
    """
    mod_ai = types.ModuleType("inspect_ai")
    mod_model = types.ModuleType("inspect_ai.model")
    mod_gen = types.ModuleType("inspect_ai.model._generate_config")

    class _Cfg:
        def __init__(self, value):
            self.max_tool_output = value

    def active_generate_config():  # noqa: N802 (external API name)
        return _Cfg(max_tool_output)

    # Attach API to stub module
    mod_gen.active_generate_config = active_generate_config  # type: ignore[attr-defined]

    # Register stubs in import system
    monkeypatch.setitem(sys.modules, "inspect_ai", mod_ai)
    monkeypatch.setitem(sys.modules, "inspect_ai.model", mod_model)
    monkeypatch.setitem(sys.modules, "inspect_ai.model._generate_config", mod_gen)


def test_limit_default_when_no_env_or_config(monkeypatch):
    from inspect_agents.observability import get_effective_tool_output_limit

    # No env
    monkeypatch.delenv("INSPECT_MAX_TOOL_OUTPUT", raising=False)

    # Active config with no limit
    _install_generate_config_stub(monkeypatch, max_tool_output=None)

    limit, source = get_effective_tool_output_limit()
    assert limit == 16 * 1024
    assert source == "default"


def test_limit_from_env_when_set(monkeypatch):
    from inspect_agents.observability import get_effective_tool_output_limit

    # Env set
    monkeypatch.setenv("INSPECT_MAX_TOOL_OUTPUT", "2048")

    # Active config with no limit
    _install_generate_config_stub(monkeypatch, max_tool_output=None)

    limit, source = get_effective_tool_output_limit()
    assert limit == 2048
    assert source == "env"


def test_limit_from_config_over_env(monkeypatch):
    from inspect_agents.observability import get_effective_tool_output_limit

    # Env set to a different value; config should take precedence
    monkeypatch.setenv("INSPECT_MAX_TOOL_OUTPUT", "2048")

    # Active config provides a limit
    _install_generate_config_stub(monkeypatch, max_tool_output=4096)

    limit, source = get_effective_tool_output_limit()
    assert limit == 4096
    assert source == "config"
