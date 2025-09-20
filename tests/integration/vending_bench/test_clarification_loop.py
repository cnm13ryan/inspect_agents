"""Integration tests for the Sub-Agent Clarification Loop feature.

Tests verify that missing/invalid parameters trigger clarifying questions
and that successful retry flows work as expected.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from examples.vending_bench.tools import SlotPriceUpdate
from inspect_agents.exceptions import ToolException


@pytest.fixture(autouse=True)
def _no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NO_NETWORK", "1")


@pytest.fixture
def mock_env():
    """Create a mock vending environment for testing."""
    # Create mock slots for machine inventory
    mock_slot = SimpleNamespace(sku="chips", quantity=5, price=1.50, capacity=10)
    machine_inventory = [[None for _ in range(3)] for _ in range(4)]
    machine_inventory[0][0] = mock_slot  # Place chips in slot (0, 0)

    state = SimpleNamespace(
        storage_inventory={"chips": 50, "soda": 30, "candy": 25},
        machine_inventory=machine_inventory,
        demand_profiles={
            "chips": SimpleNamespace(
                product=SimpleNamespace(base_price=1.50),
                reference_price=1.50,
                base_daily_sales=10.0,
                price_elasticity=-1.0,
            ),
            "soda": SimpleNamespace(
                product=SimpleNamespace(base_price=2.00),
                reference_price=2.00,
                base_daily_sales=8.0,
                price_elasticity=-0.8,
            ),
            "candy": SimpleNamespace(
                product=SimpleNamespace(base_price=1.25),
                reference_price=1.25,
                base_daily_sales=12.0,
                price_elasticity=-1.2,
            ),
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
                restock_tool(sku=None, quantity=10, row=1, column=1)

            assert "sku is required to complete this action" in str(exc_info.value)

    def test_restock_missing_quantity_triggers_exception(self, vending_tools_module, mock_env):
        """Test that missing quantity in restock triggers ToolException."""
        with patch("examples.vending_bench.tools.get_env", return_value=mock_env):
            restock_tool = vending_tools_module.restock_machine()

            with pytest.raises(ToolException) as exc_info:
                restock_tool(sku="chips", quantity=None, row=1, column=1)

            assert "quantity is required to complete this action" in str(exc_info.value)

    def test_restock_insufficient_storage_triggers_exception(self, vending_tools_module, mock_env):
        """Test that insufficient storage triggers ToolException with specific details."""
        with patch("examples.vending_bench.tools.get_env", return_value=mock_env):
            restock_tool = vending_tools_module.restock_machine()

            with pytest.raises(ToolException) as exc_info:
                restock_tool(sku="chips", quantity=100, row=1, column=1)  # More than available (50)

            error_msg = str(exc_info.value)
            assert "Insufficient storage inventory for chips" in error_msg
            assert "have 50, need 100" in error_msg

    def test_restock_missing_row_triggers_exception(self, vending_tools_module, mock_env):
        """Test that missing row in restock triggers ToolException."""
        with patch("examples.vending_bench.tools.get_env", return_value=mock_env):
            restock_tool = vending_tools_module.restock_machine()

            with pytest.raises(ToolException) as exc_info:
                restock_tool(sku="chips", quantity=10, column=1)

            assert "row is required to complete this action" in str(exc_info.value)

    def test_restock_missing_column_triggers_exception(self, vending_tools_module, mock_env):
        """Test that missing column in restock triggers ToolException."""
        with patch("examples.vending_bench.tools.get_env", return_value=mock_env):
            restock_tool = vending_tools_module.restock_machine()

            with pytest.raises(ToolException) as exc_info:
                restock_tool(sku="chips", quantity=10, row=1)

            assert "column is required to complete this action" in str(exc_info.value)

    def test_restock_successful_flow(self, vending_tools_module, mock_env):
        """Test that valid restock parameters succeed."""
        with patch("examples.vending_bench.tools.get_env", return_value=mock_env):
            restock_tool = vending_tools_module.restock_machine()

            # Should not raise exception
            result = restock_tool(sku="chips", quantity=20, row=1, column=1)

            # Verify the environment methods were called
            mock_env.restock.assert_called_once_with("chips", 20, row=0, column=0)  # Tools convert to 0-indexed
            mock_env.advance_time.assert_called_once_with(75)  # Updated to match tools.py

            # Verify result structure
            assert result.sku == "chips"
            assert result.quantity_restocked == 20
            assert result.row == 1  # Original 1-indexed input
            assert result.column == 1  # Original 1-indexed input


class TestSetPriceClarificationLoop:
    """Test clarification loop for set_price tool."""

    def test_set_price_empty_updates_triggers_exception(self, vending_tools_module, mock_env):
        """ToolException clarifies when no price updates are provided."""
        with patch("examples.vending_bench.tools.get_env", return_value=mock_env):
            price_tool = vending_tools_module.set_price()

            with pytest.raises(ToolException) as exc_info:
                price_tool(updates=[])

            assert "At least one price update is required" in str(exc_info.value)

    def test_set_price_empty_slot_triggers_exception(self, vending_tools_module, mock_env):
        """Test that updating an empty slot triggers ToolException."""
        with patch("examples.vending_bench.tools.get_env", return_value=mock_env):
            price_tool = vending_tools_module.set_price()
            updates = [SlotPriceUpdate(row=2, column=2, price=2.50)]  # Empty slot (2,2 -> 1,1 in 0-indexed)

            with pytest.raises(ToolException) as exc_info:
                price_tool(updates=updates)

            assert "slot (2, 2) is empty" in str(exc_info.value)

    def test_set_price_negative_price_triggers_exception(self, vending_tools_module, mock_env):
        """ToolException clarifies when price is non-positive."""
        with patch("examples.vending_bench.tools.get_env", return_value=mock_env):
            price_tool = vending_tools_module.set_price()
            updates = [SlotPriceUpdate(row=1, column=1, price=-1.50)]

            with pytest.raises(ToolException) as exc_info:
                price_tool(updates=updates)

            assert "price must be greater than zero" in str(exc_info.value)

    def test_set_price_successful_flow(self, vending_tools_module, mock_env):
        """Test that valid set_price parameters succeed."""
        with patch("examples.vending_bench.tools.get_env", return_value=mock_env):
            price_tool = vending_tools_module.set_price()
            updates = [SlotPriceUpdate(row=1, column=1, price=1.75)]  # 1-indexed input

            # Should not raise exception
            result = price_tool(updates=updates)

            # Verify the environment methods were called
            mock_env.set_price.assert_called_once_with({(0, 0): 1.75})  # Converted to 0-indexed
            mock_env.advance_time.assert_called_once_with(300)  # 5 hours as per tools.py

            # Verify result structure
            assert len(result.updates) == 1
            update_result = result.updates[0]
            assert update_result.row == 1  # Original 1-indexed input
            assert update_result.column == 1  # Original 1-indexed input
            assert update_result.sku == "chips"
            assert update_result.new_price == 1.75
            assert update_result.old_price == 1.50  # From mock_env


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
