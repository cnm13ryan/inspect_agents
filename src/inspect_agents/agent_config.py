"""Immutable configuration objects for agent builders.

This module provides dataclasses that centralize environment variable
resolution and configuration precedence for both supervisor and iterative
agents. These objects resolve env vars once at construction time, eliminating
redundant lookups and making configuration intent explicit.

Design principles:
- Immutable (frozen dataclasses) to prevent accidental mutation
- Resolve environment variables at construction time only
- Document source of each resolved value for observability
- Maintain backward compatibility with existing builders
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from .settings import resolve_include_defaults


@dataclass(frozen=True)
class DefaultToolsConfig:
    """Configuration for default tool inclusion.

    Attributes:
        include_defaults: Whether to include built-in tools
        source: Origin of the decision: "explicit", "env", or "default"
        env_raw: Raw environment variable value (for telemetry)
    """

    include_defaults: bool
    source: str
    env_raw: str | None

    @classmethod
    def resolve(cls, explicit: bool | None) -> DefaultToolsConfig:
        """Resolve include_defaults with env precedence.

        Args:
            explicit: Explicit value from caller (takes precedence over env)

        Returns:
            Resolved configuration with source attribution
        """
        resolved, source, env_raw = resolve_include_defaults(explicit)
        return cls(
            include_defaults=resolved,
            source=source,
            env_raw=env_raw,
        )


@dataclass(frozen=True)
class StepLimitsConfig:
    """Configuration for time and step limits.

    Attributes:
        real_time_limit_sec: Wall-clock timeout in seconds (None = unlimited)
        max_steps: Maximum iteration steps (None = unlimited)
    """

    real_time_limit_sec: int | None
    max_steps: int | None

    @classmethod
    def resolve(
        cls,
        *,
        real_time_limit_sec: int | None,
        max_steps: int | None,
    ) -> StepLimitsConfig:
        """Resolve limits with env fallback.

        Args:
            real_time_limit_sec: Explicit time limit (precedence over env)
            max_steps: Explicit step limit (precedence over env)

        Returns:
            Resolved limits (checks INSPECT_ITERATIVE_TIME_LIMIT and
            INSPECT_ITERATIVE_MAX_STEPS when args are None)
        """
        from .iterative_config import resolve_time_and_step_limits

        time_limit, step_limit = resolve_time_and_step_limits(
            real_time_limit_sec=real_time_limit_sec,
            max_steps=max_steps,
        )
        return cls(
            real_time_limit_sec=time_limit,
            max_steps=step_limit,
        )


@dataclass(frozen=True)
class PruningConfig:
    """Configuration for conversation pruning.

    Attributes:
        prune_after_messages: Trigger pruning after this many messages (None = disabled)
        prune_keep_last: Number of recent messages to retain when pruning
    """

    prune_after_messages: int | None
    prune_keep_last: int

    @classmethod
    def resolve(
        cls,
        *,
        prune_after_messages: int | None,
        prune_keep_last: int,
    ) -> PruningConfig:
        """Resolve pruning config with env overrides.

        Args:
            prune_after_messages: Trigger threshold (None or 120 => check env)
            prune_keep_last: Retain count (40 => check env)

        Returns:
            Resolved config (honors INSPECT_PRUNE_AFTER_MESSAGES and
            INSPECT_PRUNE_KEEP_LAST when defaults are used)
        """
        from .iterative_config import resolve_pruning

        eff_after, eff_keep = resolve_pruning(
            prune_after_messages=prune_after_messages,
            prune_keep_last=prune_keep_last,
        )
        return cls(
            prune_after_messages=eff_after,
            prune_keep_last=eff_keep,
        )


@dataclass(frozen=True)
class TruncationConfig:
    """Configuration for per-message token truncation.

    Attributes:
        per_msg_token_cap: Max tokens per message (None = disabled)
        truncate_last_k: Number of recent messages to apply truncation to
    """

    per_msg_token_cap: int | None
    truncate_last_k: int

    @classmethod
    def resolve(
        cls,
        *,
        per_msg_token_cap: int | None,
        truncate_last_k: int,
    ) -> TruncationConfig:
        """Resolve truncation config with env overrides.

        Args:
            per_msg_token_cap: Per-message cap (None => check env)
            truncate_last_k: Window size (check env if >0)

        Returns:
            Resolved config (honors INSPECT_PER_MSG_TOKEN_CAP and
            INSPECT_TRUNCATE_LAST_K)
        """
        from .iterative_config import resolve_truncation

        eff_cap, eff_last_k = resolve_truncation(
            per_msg_token_cap=per_msg_token_cap,
            truncate_last_k=truncate_last_k,
        )
        return cls(
            per_msg_token_cap=eff_cap,
            truncate_last_k=eff_last_k,
        )


@dataclass(frozen=True)
class RetryConfig:
    """Configuration for model generate() retry behavior.

    Attributes:
        max_attempts: Maximum retry attempts (including first try)
        initial_backoff_s: Initial backoff delay in seconds
        max_backoff_s: Maximum backoff delay cap in seconds
        jitter_s: Jitter range in seconds (0 = disabled)
        retry_predicate: Optional exception classifier (None = use default)
    """

    max_attempts: int | None
    initial_backoff_s: float | None
    max_backoff_s: float | None
    jitter_s: float | None
    retry_predicate: Callable[[BaseException], bool] | None

    @classmethod
    def from_args(
        cls,
        *,
        retry_max_attempts: int | None = None,
        retry_initial_backoff_s: float | None = None,
        retry_max_backoff_s: float | None = None,
        retry_jitter_s: float | None = None,
        retry_predicate: Callable[[BaseException], bool] | None = None,
    ) -> RetryConfig:
        """Create config from explicit arguments.

        Env resolution is deferred to generate_with_retry_time() for backward
        compatibility, but this object ensures we pass config consistently.

        Args:
            retry_max_attempts: Max attempts (None => defer to env/defaults)
            retry_initial_backoff_s: Initial backoff (None => defer to env)
            retry_max_backoff_s: Max backoff (None => defer to env)
            retry_jitter_s: Jitter range (None => defer to env)
            retry_predicate: Custom exception filter (None => default predicate)

        Returns:
            Immutable retry configuration
        """
        return cls(
            max_attempts=retry_max_attempts,
            initial_backoff_s=retry_initial_backoff_s,
            max_backoff_s=retry_max_backoff_s,
            jitter_s=retry_jitter_s,
            retry_predicate=retry_predicate,
        )


@dataclass(frozen=True)
class IterativeAgentConfig:
    """Consolidated configuration for iterative agents.

    This object bundles all environment-resolved settings for
    build_iterative_agent, eliminating repeated env lookups and clarifying
    configuration precedence.

    Attributes:
        defaults: Default tool inclusion config
        limits: Time and step limits
        pruning: Conversation pruning settings
        truncation: Per-message token truncation settings
        retry: Model retry behavior
        max_tool_output_bytes: Global tool output cap (None => check env)
    """

    defaults: DefaultToolsConfig
    limits: StepLimitsConfig
    pruning: PruningConfig
    truncation: TruncationConfig
    retry: RetryConfig
    max_tool_output_bytes: int | None

    @classmethod
    def resolve(
        cls,
        *,
        # Default tools
        include_defaults: bool | None = None,
        # Time/step limits
        real_time_limit_sec: int | None = None,
        max_steps: int | None = None,
        # Pruning
        prune_after_messages: int | None = 120,
        prune_keep_last: int = 40,
        # Truncation
        per_msg_token_cap: int | None = None,
        truncate_last_k: int = 200,
        # Retry
        retry_max_attempts: int | None = None,
        retry_initial_backoff_s: float | None = None,
        retry_max_backoff_s: float | None = None,
        retry_jitter_s: float | None = None,
        retry_predicate: Callable[[BaseException], bool] | None = None,
        # Tool output
        max_tool_output_bytes: int | None = None,
    ) -> IterativeAgentConfig:
        """Resolve all configuration with environment precedence.

        This method centralizes all env var lookups into a single immutable
        object, ensuring consistent resolution logic.

        Args:
            include_defaults: Whether to include built-in tools
            real_time_limit_sec: Wall-clock timeout
            max_steps: Max iteration steps
            prune_after_messages: Pruning trigger threshold
            prune_keep_last: Messages to retain when pruning
            per_msg_token_cap: Per-message token limit
            truncate_last_k: Window for truncation
            retry_max_attempts: Max retry attempts
            retry_initial_backoff_s: Initial retry delay
            retry_max_backoff_s: Max retry delay
            retry_jitter_s: Retry jitter range
            retry_predicate: Custom retry exception filter
            max_tool_output_bytes: Global tool output limit

        Returns:
            Immutable configuration bundle with all env vars resolved
        """
        return cls(
            defaults=DefaultToolsConfig.resolve(include_defaults),
            limits=StepLimitsConfig.resolve(
                real_time_limit_sec=real_time_limit_sec,
                max_steps=max_steps,
            ),
            pruning=PruningConfig.resolve(
                prune_after_messages=prune_after_messages,
                prune_keep_last=prune_keep_last,
            ),
            truncation=TruncationConfig.resolve(
                per_msg_token_cap=per_msg_token_cap,
                truncate_last_k=truncate_last_k,
            ),
            retry=RetryConfig.from_args(
                retry_max_attempts=retry_max_attempts,
                retry_initial_backoff_s=retry_initial_backoff_s,
                retry_max_backoff_s=retry_max_backoff_s,
                retry_jitter_s=retry_jitter_s,
                retry_predicate=retry_predicate,
            ),
            max_tool_output_bytes=max_tool_output_bytes,
        )


@dataclass(frozen=True)
class SupervisorConfig:
    """Consolidated configuration for supervisor agents.

    Simpler than IterativeAgentConfig as supervisors have fewer configuration
    surfaces (no pruning, truncation, or limits).

    Attributes:
        defaults: Default tool inclusion config
        retry: Model retry behavior (if supervisor uses retries in future)
    """

    defaults: DefaultToolsConfig

    @classmethod
    def resolve(
        cls,
        *,
        include_defaults: bool | None = None,
    ) -> SupervisorConfig:
        """Resolve supervisor configuration.

        Args:
            include_defaults: Whether to include built-in tools

        Returns:
            Immutable supervisor configuration
        """
        return cls(
            defaults=DefaultToolsConfig.resolve(include_defaults),
        )


__all__ = [
    "DefaultToolsConfig",
    "StepLimitsConfig",
    "PruningConfig",
    "TruncationConfig",
    "RetryConfig",
    "IterativeAgentConfig",
    "SupervisorConfig",
]
