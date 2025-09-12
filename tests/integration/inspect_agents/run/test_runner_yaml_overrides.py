"""Expose example runner YAML overrides tests under consolidated `run/` path.

This wrapper allows focused execution via:

    pytest -q tests/integration/inspect_agents/run

and keyword selection:

    pytest -q -k runner

The original test module remains in place; this file re-exports its tests
without modifying semantics to respect area constraints.
"""

from tests.integration.examples.run.test_runner_yaml_overrides import *  # noqa: F401,F403
