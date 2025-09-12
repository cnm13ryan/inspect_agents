"""Expose example runner model flags tests under consolidated `run/` path.

This wrapper re-exports tests without changing behavior to keep edits
confined to the `run/` area.
"""

from tests.integration.examples.test_runner_model_flags import *  # noqa: F401,F403
