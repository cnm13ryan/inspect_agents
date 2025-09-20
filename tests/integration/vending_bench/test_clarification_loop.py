"""Integration tests for the Sub-Agent Clarification Loop feature.

Tests verify that missing/invalid parameters trigger clarifying questions
and that successful retry flows work as expected.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from inspect_agents.exceptions import ToolException


@pytest.fixture(autouse=True)
def _no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NO_NETWORK", "1")


@pytest.fixture
def mock_env():
    """Create a mock vending environment for testing."""
    state = SimpleNamespace(
        storage_inventory={"chips": 50, "soda": 30, "candy": 25},
        machine_inventory={"chips": 10, "soda": 5, "candy": 8},
        demand_profiles={
            "chips": SimpleNamespace(product=SimpleNamespace(base_price=1.50)),
            "soda": SimpleNamespace(product=SimpleNamespace(base_price=2.00)),
            "candy": SimpleNamespace(product=SimpleNamespace(base_price=1.25)),
        },
        prices={"chips": 1.50, "soda": 2.00, "candy": 1.25},
    )
    env = SimpleNamespace(state=state)
    env.restock = MagicMock()
    env.set_price = MagicMock()
    env.advance_time = MagicMock()
    return env


@pytest.fixture
def vending_tools_module(monkeypatch: pytest.MonkeyPatch):
    """Import and return the vending tools module with mocked environment."""
    import importlib
    import sys
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[3]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    # Import the tools module
    tools_module = importlib.import_module("examples.vending_bench.tools")
    return tools_module


class TestToolValidationExceptions:
    """Test that tool validation functions raise appropriate ToolExceptions."""

    def test_require_non_empty_string_with_none(self, vending_tools_module):
        """Test that None values trigger ToolException with clear message."""
        with pytest.raises(ToolException) as exc_info:
            vending_tools_module._require_non_empty_string("sku", None)

        assert "sku is required to complete this action" in str(exc_info.value)
        assert "Please provide the sku" in str(exc_info.value)

    def test_require_non_empty_string_with_empty(self, vending_tools_module):
        """Test that empty strings trigger ToolException with clear message."""
        with pytest.raises(ToolException) as exc_info:
            vending_tools_module._require_non_empty_string("sku", "  ")

        assert "sku cannot be empty" in str(exc_info.value)
        assert "Please provide a specific sku" in str(exc_info.value)

    def test_require_positive_int_with_none(self, vending_tools_module):
        """Test that None quantity triggers ToolException with clear message."""
        with pytest.raises(ToolException) as exc_info:
            vending_tools_module._require_positive_int("quantity", None)

        assert "quantity is required to complete this action" in str(exc_info.value)
        assert "Please provide the quantity" in str(exc_info.value)

    def test_require_positive_int_with_zero(self, vending_tools_module):
        """Test that zero quantity triggers ToolException with clear message."""
        with pytest.raises(ToolException) as exc_info:
            vending_tools_module._require_positive_int("quantity", 0)

        assert "quantity must be greater than zero" in str(exc_info.value)
        assert "Please provide a positive value for quantity" in str(exc_info.value)

    def test_require_positive_int_with_negative(self, vending_tools_module):
        """Test that negative quantity triggers ToolException with clear message."""
        with pytest.raises(ToolException) as exc_info:
            vending_tools_module._require_positive_int("quantity", -5)

        assert "quantity must be greater than zero" in str(exc_info.value)

    def test_require_positive_float_with_none(self, vending_tools_module):
        """Test that None price triggers ToolException with clear message."""
        with pytest.raises(ToolException) as exc_info:
            vending_tools_module._require_positive_float("price", None)

        assert "price is required to complete this action" in str(exc_info.value)
        assert "Please provide the price" in str(exc_info.value)

    def test_require_positive_float_with_zero(self, vending_tools_module):
        """Test that zero price triggers ToolException with clear message."""
        with pytest.raises(ToolException) as exc_info:
            vending_tools_module._require_positive_float("price", 0.0)

        assert "price must be greater than zero" in str(exc_info.value)

    def test_require_known_sku_with_unknown(self, vending_tools_module, mock_env):
        """Test that unknown SKU triggers ToolException with suggestions."""
        with pytest.raises(ToolException) as exc_info:
            vending_tools_module._require_known_sku(mock_env, "unknown_sku")

        error_msg = str(exc_info.value)
        assert "Unknown SKU 'unknown_sku'" in error_msg
        assert "Please choose a valid SKU" in error_msg
        assert "candy, chips, soda" in error_msg  # alphabetically sorted


class TestRestockMachineClarificationLoop:
    """Test clarification loop for restock_machine tool."""

    def test_restock_missing_sku_triggers_exception(self, vending_tools_module, mock_env):
        """Test that missing SKU in restock triggers ToolException."""
        with patch("examples.vending_bench.tools.get_env", return_value=mock_env):
            restock_tool = vending_tools_module.restock_machine()

            with pytest.raises(ToolException) as exc_info:
                restock_tool(sku=None, quantity=10)

            assert "sku is required to complete this action" in str(exc_info.value)

    def test_restock_missing_quantity_triggers_exception(self, vending_tools_module, mock_env):
        """Test that missing quantity in restock triggers ToolException."""
        with patch("examples.vending_bench.tools.get_env", return_value=mock_env):
            restock_tool = vending_tools_module.restock_machine()

            with pytest.raises(ToolException) as exc_info:
                restock_tool(sku="chips", quantity=None)

            assert "quantity is required to complete this action" in str(exc_info.value)

    def test_restock_insufficient_storage_triggers_exception(self, vending_tools_module, mock_env):
        """Test that insufficient storage triggers ToolException with specific details."""
        with patch("examples.vending_bench.tools.get_env", return_value=mock_env):
            restock_tool = vending_tools_module.restock_machine()

            with pytest.raises(ToolException) as exc_info:
                restock_tool(sku="chips", quantity=100)  # More than available (50)

            error_msg = str(exc_info.value)
            assert "Insufficient storage inventory for chips" in error_msg
            assert "have 50, need 100" in error_msg

    def test_restock_successful_flow(self, vending_tools_module, mock_env):
        """Test that valid restock parameters succeed."""
        with patch("examples.vending_bench.tools.get_env", return_value=mock_env):
            restock_tool = vending_tools_module.restock_machine()

            # Should not raise exception
            result = restock_tool(sku="chips", quantity=20)

            # Verify the environment methods were called
            mock_env.restock.assert_called_once_with("chips", 20)
            mock_env.advance_time.assert_called_once_with(15)

            # Verify result structure
            assert result.sku == "chips"
            assert result.quantity_restocked == 20


class TestSetPriceClarificationLoop:
    """Test clarification loop for set_price tool."""

    def test_set_price_missing_sku_triggers_exception(self, vending_tools_module, mock_env):
        """Test that missing SKU in set_price triggers ToolException."""
        with patch("examples.vending_bench.tools.get_env", return_value=mock_env):
            price_tool = vending_tools_module.set_price()

            with pytest.raises(ToolException) as exc_info:
                price_tool(sku=None, price=2.50)

            assert "sku is required to complete this action" in str(exc_info.value)

    def test_set_price_missing_price_triggers_exception(self, vending_tools_module, mock_env):
        """Test that missing price in set_price triggers ToolException."""
        with patch("examples.vending_bench.tools.get_env", return_value=mock_env):
            price_tool = vending_tools_module.set_price()

            with pytest.raises(ToolException) as exc_info:
                price_tool(sku="chips", price=None)

            assert "price is required to complete this action" in str(exc_info.value)

    def test_set_price_negative_price_triggers_exception(self, vending_tools_module, mock_env):
        """Test that negative price triggers ToolException."""
        with patch("examples.vending_bench.tools.get_env", return_value=mock_env):
            price_tool = vending_tools_module.set_price()

            with pytest.raises(ToolException) as exc_info:
                price_tool(sku="chips", price=-1.50)

            assert "price must be greater than zero" in str(exc_info.value)

    def test_set_price_successful_flow(self, vending_tools_module, mock_env):
        """Test that valid set_price parameters succeed."""
        with patch("examples.vending_bench.tools.get_env", return_value=mock_env):
            price_tool = vending_tools_module.set_price()

            # Should not raise exception
            result = price_tool(sku="chips", price=1.75)

            # Verify the environment methods were called
            mock_env.set_price.assert_called_once_with("chips", 1.75)
            mock_env.advance_time.assert_called_once_with(5)

            # Verify result structure
            assert result.sku == "chips"
            assert result.new_price == 1.75
            assert result.old_price == 1.50  # From mock_env


class TestPlaceOrderClarificationLoop:
    """Test clarification loop for place_order tool."""

    def test_place_order_missing_sku_triggers_exception(self, vending_tools_module, mock_env):
        """Test that missing SKU in place_order triggers ToolException."""
        with patch("examples.vending_bench.tools.get_env", return_value=mock_env):
            order_tool = vending_tools_module.place_order()

            with pytest.raises(ToolException) as exc_info:
                order_tool(sku=None, quantity=50)

            assert "sku is required to complete this action" in str(exc_info.value)

    def test_place_order_missing_quantity_triggers_exception(self, vending_tools_module, mock_env):
        """Test that missing quantity in place_order triggers ToolException."""
        with patch("examples.vending_bench.tools.get_env", return_value=mock_env):
            order_tool = vending_tools_module.place_order()

            with pytest.raises(ToolException) as exc_info:
                order_tool(sku="chips", quantity=None)

            assert "quantity is required to complete this action" in str(exc_info.value)


class TestClarificationLoopIntegration:
    """Integration tests for the full clarification loop behavior."""

    def test_transfer_to_vending_with_missing_parameters(self, monkeypatch: pytest.MonkeyPatch):
        """Test that transfer_to_vending handles ToolExceptions gracefully."""
        # This test would require more complex setup with actual agent execution
        # For now, we verify the tool validation is working correctly
        pass

    def test_physical_agent_prompt_mentions_clarification(self, monkeypatch: pytest.MonkeyPatch):
        """Test that the physical agent prompt includes clarification guidance."""
        import importlib
        import sys
        from pathlib import Path

        repo_root = Path(__file__).resolve().parents[3]
        if str(repo_root) not in sys.path:
            sys.path.insert(0, str(repo_root))

        prompts_module = importlib.import_module("examples.vending_bench.prompts")
        prompt = prompts_module.PHYSICAL_AGENT_PROMPT

        # Verify clarification guidance is present
        assert "ask the supervisor for clarification" in prompt
        assert "Which product SKU should I use?" in prompt
        assert "How many units should I process?" in prompt
        assert "What price should I set?" in prompt
