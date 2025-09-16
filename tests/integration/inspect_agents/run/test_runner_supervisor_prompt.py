"""Expose example runner supervisor prompt tests under consolidated `run/` path.

Re-exports tests from the original module to enable grouped selection
without touching files outside this area.
"""

from tests.integration.examples.test_runner_supervisor_prompt import *  # noqa: F401,F403
