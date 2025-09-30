"""Unit tests for agent configuration dataclasses."""

import pytest

from inspect_agents.agent_config import (
    DefaultToolsConfig,
    IterativeAgentConfig,
    PruningConfig,
    RetryConfig,
    StepLimitsConfig,
    SupervisorConfig,
    TruncationConfig,
)


class TestDefaultToolsConfig:
    """Tests for DefaultToolsConfig resolution."""

    def test_explicit_true_overrides_env(self, monkeypatch):
        """Explicit argument takes precedence over environment."""
        monkeypatch.setenv("INSPECT_AGENTS_INCLUDE_DEFAULT_TOOLS", "false")
        cfg = DefaultToolsConfig.resolve(explicit=True)
        assert cfg.include_defaults is True
        assert cfg.source == "explicit"
        assert cfg.env_raw == "false"

    def test_explicit_false_overrides_env(self, monkeypatch):
        """Explicit False takes precedence over environment."""
        monkeypatch.setenv("INSPECT_AGENTS_INCLUDE_DEFAULT_TOOLS", "true")
        cfg = DefaultToolsConfig.resolve(explicit=False)
        assert cfg.include_defaults is False
        assert cfg.source == "explicit"
        assert cfg.env_raw == "true"

    def test_env_true_when_no_explicit(self, monkeypatch):
        """Environment value is used when explicit is None."""
        monkeypatch.setenv("INSPECT_AGENTS_INCLUDE_DEFAULT_TOOLS", "true")
        cfg = DefaultToolsConfig.resolve(explicit=None)
        assert cfg.include_defaults is True
        assert cfg.source == "env"
        assert cfg.env_raw == "true"

    def test_env_false_when_no_explicit(self, monkeypatch):
        """Environment false is used when explicit is None."""
        monkeypatch.setenv("INSPECT_AGENTS_INCLUDE_DEFAULT_TOOLS", "0")
        cfg = DefaultToolsConfig.resolve(explicit=None)
        assert cfg.include_defaults is False
        assert cfg.source == "env"
        assert cfg.env_raw == "0"

    def test_default_true_when_no_env_or_explicit(self, monkeypatch):
        """Default to True when neither env nor explicit is provided."""
        monkeypatch.delenv("INSPECT_AGENTS_INCLUDE_DEFAULT_TOOLS", raising=False)
        cfg = DefaultToolsConfig.resolve(explicit=None)
        assert cfg.include_defaults is True
        assert cfg.source == "default"
        assert cfg.env_raw is None

    def test_immutability(self):
        """Config objects are immutable (frozen)."""
        cfg = DefaultToolsConfig.resolve(explicit=True)
        with pytest.raises(Exception):  # FrozenInstanceError or similar
            cfg.include_defaults = False  # type: ignore[misc]


class TestStepLimitsConfig:
    """Tests for StepLimitsConfig resolution."""

    def test_explicit_args_override_env(self, monkeypatch):
        """Explicit arguments take precedence over environment."""
        monkeypatch.setenv("INSPECT_ITERATIVE_TIME_LIMIT", "10")
        monkeypatch.setenv("INSPECT_ITERATIVE_MAX_STEPS", "20")
        cfg = StepLimitsConfig.resolve(real_time_limit_sec=99, max_steps=88)
        assert cfg.real_time_limit_sec == 99
        assert cfg.max_steps == 88

    def test_env_fallback_when_args_none(self, monkeypatch):
        """Environment values are used when args are None."""
        monkeypatch.setenv("INSPECT_ITERATIVE_TIME_LIMIT", "30")
        monkeypatch.setenv("INSPECT_ITERATIVE_MAX_STEPS", "40")
        cfg = StepLimitsConfig.resolve(real_time_limit_sec=None, max_steps=None)
        assert cfg.real_time_limit_sec == 30
        assert cfg.max_steps == 40

    def test_nonpositive_env_yields_none(self, monkeypatch):
        """Non-positive env values result in None limits."""
        monkeypatch.setenv("INSPECT_ITERATIVE_TIME_LIMIT", "0")
        monkeypatch.setenv("INSPECT_ITERATIVE_MAX_STEPS", "-5")
        cfg = StepLimitsConfig.resolve(real_time_limit_sec=None, max_steps=None)
        assert cfg.real_time_limit_sec is None
        assert cfg.max_steps is None

    def test_no_env_or_args_yields_none(self, monkeypatch):
        """No env or args results in None limits."""
        monkeypatch.delenv("INSPECT_ITERATIVE_TIME_LIMIT", raising=False)
        monkeypatch.delenv("INSPECT_ITERATIVE_MAX_STEPS", raising=False)
        cfg = StepLimitsConfig.resolve(real_time_limit_sec=None, max_steps=None)
        assert cfg.real_time_limit_sec is None
        assert cfg.max_steps is None


class TestPruningConfig:
    """Tests for PruningConfig resolution."""

    def test_explicit_non_default_ignores_env(self, monkeypatch):
        """Explicit non-default args ignore environment."""
        monkeypatch.setenv("INSPECT_PRUNE_AFTER_MESSAGES", "100")
        monkeypatch.setenv("INSPECT_PRUNE_KEEP_LAST", "50")
        cfg = PruningConfig.resolve(prune_after_messages=80, prune_keep_last=30)
        assert cfg.prune_after_messages == 80
        assert cfg.prune_keep_last == 30

    def test_env_applies_when_default_args(self, monkeypatch):
        """Environment overrides when default values are used."""
        monkeypatch.setenv("INSPECT_PRUNE_AFTER_MESSAGES", "150")
        monkeypatch.setenv("INSPECT_PRUNE_KEEP_LAST", "60")
        cfg = PruningConfig.resolve(prune_after_messages=120, prune_keep_last=40)
        assert cfg.prune_after_messages == 150
        assert cfg.prune_keep_last == 60

    def test_nonpositive_prune_after_becomes_none(self, monkeypatch):
        """Non-positive INSPECT_PRUNE_AFTER_MESSAGES disables pruning."""
        monkeypatch.setenv("INSPECT_PRUNE_AFTER_MESSAGES", "0")
        cfg = PruningConfig.resolve(prune_after_messages=120, prune_keep_last=40)
        assert cfg.prune_after_messages is None
        assert cfg.prune_keep_last == 40

    def test_negative_keep_last_clamps_to_zero(self, monkeypatch):
        """Negative INSPECT_PRUNE_KEEP_LAST clamps to 0."""
        monkeypatch.setenv("INSPECT_PRUNE_KEEP_LAST", "-10")
        cfg = PruningConfig.resolve(prune_after_messages=120, prune_keep_last=40)
        assert cfg.prune_keep_last == 0


class TestTruncationConfig:
    """Tests for TruncationConfig resolution."""

    def test_explicit_cap_overrides_env(self, monkeypatch):
        """Explicit per_msg_token_cap overrides environment."""
        monkeypatch.setenv("INSPECT_PER_MSG_TOKEN_CAP", "999")
        cfg = TruncationConfig.resolve(per_msg_token_cap=100, truncate_last_k=200)
        assert cfg.per_msg_token_cap == 100
        assert cfg.truncate_last_k == 200

    def test_env_cap_when_arg_none(self, monkeypatch):
        """Environment cap is used when arg is None."""
        monkeypatch.setenv("INSPECT_PER_MSG_TOKEN_CAP", "777")
        cfg = TruncationConfig.resolve(per_msg_token_cap=None, truncate_last_k=200)
        assert cfg.per_msg_token_cap == 777

    def test_env_last_k_overrides_arg(self, monkeypatch):
        """Environment INSPECT_TRUNCATE_LAST_K overrides arg when set."""
        monkeypatch.setenv("INSPECT_TRUNCATE_LAST_K", "50")
        cfg = TruncationConfig.resolve(per_msg_token_cap=None, truncate_last_k=200)
        assert cfg.truncate_last_k == 50

    def test_zero_last_k_env_preserves_arg(self, monkeypatch):
        """Zero or non-positive env last_k preserves arg."""
        monkeypatch.setenv("INSPECT_TRUNCATE_LAST_K", "0")
        cfg = TruncationConfig.resolve(per_msg_token_cap=None, truncate_last_k=300)
        assert cfg.truncate_last_k == 300


class TestRetryConfig:
    """Tests for RetryConfig construction."""

    def test_from_args_all_none(self):
        """RetryConfig can be created with all None values."""
        cfg = RetryConfig.from_args()
        assert cfg.max_attempts is None
        assert cfg.initial_backoff_s is None
        assert cfg.max_backoff_s is None
        assert cfg.jitter_s is None
        assert cfg.retry_predicate is None

    def test_from_args_explicit_values(self):
        """RetryConfig preserves explicit values."""

        def custom_pred(ex: BaseException) -> bool:
            return False

        cfg = RetryConfig.from_args(
            retry_max_attempts=10,
            retry_initial_backoff_s=2.0,
            retry_max_backoff_s=30.0,
            retry_jitter_s=0.5,
            retry_predicate=custom_pred,
        )
        assert cfg.max_attempts == 10
        assert cfg.initial_backoff_s == 2.0
        assert cfg.max_backoff_s == 30.0
        assert cfg.jitter_s == 0.5
        assert cfg.retry_predicate is custom_pred

    def test_immutability(self):
        """RetryConfig is immutable."""
        cfg = RetryConfig.from_args(retry_max_attempts=5)
        with pytest.raises(Exception):  # FrozenInstanceError
            cfg.max_attempts = 10  # type: ignore[misc]


class TestIterativeAgentConfig:
    """Tests for IterativeAgentConfig consolidation."""

    def test_resolve_all_defaults(self, monkeypatch):
        """Resolve with all default arguments."""
        monkeypatch.delenv("INSPECT_AGENTS_INCLUDE_DEFAULT_TOOLS", raising=False)
        monkeypatch.delenv("INSPECT_ITERATIVE_TIME_LIMIT", raising=False)
        monkeypatch.delenv("INSPECT_ITERATIVE_MAX_STEPS", raising=False)
        monkeypatch.delenv("INSPECT_PRUNE_AFTER_MESSAGES", raising=False)
        monkeypatch.delenv("INSPECT_PRUNE_KEEP_LAST", raising=False)
        monkeypatch.delenv("INSPECT_PER_MSG_TOKEN_CAP", raising=False)

        cfg = IterativeAgentConfig.resolve()

        # Check sub-configs are present
        assert cfg.defaults.include_defaults is True
        assert cfg.defaults.source == "default"
        assert cfg.limits.real_time_limit_sec is None
        assert cfg.limits.max_steps is None
        assert cfg.pruning.prune_after_messages == 120
        assert cfg.pruning.prune_keep_last == 40
        assert cfg.truncation.per_msg_token_cap is None
        assert cfg.truncation.truncate_last_k == 200
        assert cfg.retry.max_attempts is None
        assert cfg.max_tool_output_bytes is None

    def test_resolve_all_explicit(self, monkeypatch):
        """Resolve with all explicit arguments."""
        monkeypatch.setenv("INSPECT_AGENTS_INCLUDE_DEFAULT_TOOLS", "false")
        monkeypatch.setenv("INSPECT_ITERATIVE_TIME_LIMIT", "99")
        monkeypatch.setenv("INSPECT_ITERATIVE_MAX_STEPS", "88")

        def pred(ex: BaseException) -> bool:
            return True

        cfg = IterativeAgentConfig.resolve(
            include_defaults=True,
            real_time_limit_sec=100,
            max_steps=50,
            prune_after_messages=80,
            prune_keep_last=20,
            per_msg_token_cap=500,
            truncate_last_k=100,
            retry_max_attempts=3,
            retry_initial_backoff_s=1.5,
            retry_max_backoff_s=20.0,
            retry_jitter_s=0.2,
            retry_predicate=pred,
            max_tool_output_bytes=10000,
        )

        # Explicit values override env
        assert cfg.defaults.include_defaults is True
        assert cfg.defaults.source == "explicit"
        assert cfg.limits.real_time_limit_sec == 100
        assert cfg.limits.max_steps == 50
        assert cfg.pruning.prune_after_messages == 80
        assert cfg.pruning.prune_keep_last == 20
        assert cfg.truncation.per_msg_token_cap == 500
        assert cfg.truncation.truncate_last_k == 100
        assert cfg.retry.max_attempts == 3
        assert cfg.retry.initial_backoff_s == 1.5
        assert cfg.retry.max_backoff_s == 20.0
        assert cfg.retry.jitter_s == 0.2
        assert cfg.retry.retry_predicate is pred
        assert cfg.max_tool_output_bytes == 10000

    def test_resolve_mixed_env_and_explicit(self, monkeypatch):
        """Mix of env and explicit arguments."""
        monkeypatch.setenv("INSPECT_ITERATIVE_TIME_LIMIT", "300")
        monkeypatch.setenv("INSPECT_PRUNE_AFTER_MESSAGES", "200")

        cfg = IterativeAgentConfig.resolve(
            include_defaults=False,
            max_steps=100,
        )

        # Explicit include_defaults and max_steps
        assert cfg.defaults.include_defaults is False
        assert cfg.limits.max_steps == 100
        # Env-provided time_limit
        assert cfg.limits.real_time_limit_sec == 300
        # Default prune args trigger env override
        assert cfg.pruning.prune_after_messages == 200
        assert cfg.pruning.prune_keep_last == 40

    def test_immutability(self):
        """IterativeAgentConfig is immutable."""
        cfg = IterativeAgentConfig.resolve()
        with pytest.raises(Exception):  # FrozenInstanceError
            cfg.max_tool_output_bytes = 5000  # type: ignore[misc]


class TestSupervisorConfig:
    """Tests for SupervisorConfig resolution."""

    def test_resolve_default(self, monkeypatch):
        """SupervisorConfig resolves include_defaults only."""
        monkeypatch.delenv("INSPECT_AGENTS_INCLUDE_DEFAULT_TOOLS", raising=False)
        cfg = SupervisorConfig.resolve()
        assert cfg.defaults.include_defaults is True
        assert cfg.defaults.source == "default"

    def test_resolve_explicit(self, monkeypatch):
        """SupervisorConfig honors explicit include_defaults."""
        monkeypatch.setenv("INSPECT_AGENTS_INCLUDE_DEFAULT_TOOLS", "true")
        cfg = SupervisorConfig.resolve(include_defaults=False)
        assert cfg.defaults.include_defaults is False
        assert cfg.defaults.source == "explicit"

    def test_immutability(self):
        """SupervisorConfig is immutable."""
        cfg = SupervisorConfig.resolve()
        with pytest.raises(Exception):  # FrozenInstanceError
            cfg.defaults = DefaultToolsConfig.resolve(True)  # type: ignore[misc]
