import importlib

import pytest

from tests.fixtures.patching import patch_use_site


def test_patch_use_site_enforces_signature_and_executes_side_effect():
    # Correct replacement with matching signature works and returns sentinel
    def correct() -> list[str]:
        return ["OK"]

    with patch_use_site("inspect_agents.approval.handoff_exclusive_policy", new=correct):
        mod = importlib.import_module("inspect_agents.approval")
        assert mod.handoff_exclusive_policy() == ["OK"]


def test_patch_use_site_signature_mismatch_raises_typeerror():
    # Wrong replacement that requires an argument should fail under autospec
    def wrong(_unused: object) -> list[str]:  # signature does not match
        return ["BAD"]

    with patch_use_site("inspect_agents.approval.handoff_exclusive_policy", new=wrong):
        mod = importlib.import_module("inspect_agents.approval")
        with pytest.raises(TypeError):
            mod.handoff_exclusive_policy()  # patched proxy enforces original signature
