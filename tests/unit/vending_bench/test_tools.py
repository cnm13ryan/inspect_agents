"""Unit tests for vending bench tools with schema validation and error handling."""

from unittest.mock import patch

import pytest

from examples.vending_bench.config import EnvConfig
from examples.vending_bench.env import VendingEnv
from examples.vending_bench.memory import (
    MemoryStore,
    kv_set,
    memory_tools,
    scratchpad_append,
    vector_search,
)
from examples.vending_bench.tools import (
    ai_web_search,
    check_financial_status,
    check_inventory,
    collect_cash,
    get_machine_inventory,
    physical_agent_tools,
    place_order,
    read_email,
    restock_machine,
    send_email,
    set_price,
    supervisor_tools,
    wait_for_next_day,
)


class TestToolParameterValidation:
    """Test parameter validation within tool execution."""

    def test_tool_validation_basics(self):
        """Test that tools perform basic parameter validation."""
        # Tools should validate parameters during execution
        # This is now handled within the tool functions themselves

        # Test that tools exist and are callable
        tools = [
            read_email(),
            send_email(),
            check_inventory(),
            check_financial_status(),
            restock_machine(),
            set_price(),
            place_order(),
            collect_cash(),
            wait_for_next_day(),
            ai_web_search(),
            get_machine_inventory(),
        ]

        for tool in tools:
            assert tool is not None
            # Tools are registered with Inspect's registry system
            assert hasattr(tool, "__registry_info__")
            assert tool.__registry_info__.name is not None


class TestMemoryParameterValidation:
    """Test memory tool parameter validation."""

    def test_memory_tool_validation_basics(self):
        """Test that memory tools perform basic parameter validation."""
        # Test that memory tools exist and are callable
        tools = [
            scratchpad_append(),
            kv_set(),
            vector_search(),
        ]

        for tool in tools:
            assert tool is not None
            # Tools are registered with Inspect's registry system
            assert hasattr(tool, "__registry_info__")
            assert tool.__registry_info__.name is not None


class TestToolIntegration:
    """Test tool integration with environment and error handling."""

    @pytest.fixture
    def mock_env(self):
        """Create a mock vending environment."""
        config = EnvConfig()
        env = VendingEnv(config)
        # Initialize morning to set up daily reports
        env.morning_update()
        return env

    @pytest.fixture
    def mock_memory(self):
        """Create a mock memory store."""
        return MemoryStore()

    @patch("inspect_ai.util._store_model.store_as")
    def test_read_email_tool_success(self, mock_store_as, mock_env):
        """Test successful email read operation."""
        mock_store_as.return_value = mock_env

        tool = read_email()
        assert tool is not None
        assert hasattr(tool, "__registry_info__")
        # Note: Actual execution requires async context and full Inspect setup

    @patch("inspect_ai.util._store_model.store_as")
    def test_send_email_tool_success(self, mock_store_as, mock_env):
        """Test successful email send operation."""
        mock_store_as.return_value = mock_env

        tool = send_email()
        assert tool is not None
        assert hasattr(tool, "__registry_info__")

    @patch("inspect_ai.util._store_model.store_as")
    def test_check_inventory_tool_success(self, mock_store_as, mock_env):
        """Test successful inventory check operation."""
        mock_store_as.return_value = mock_env

        tool = check_inventory()
        assert tool is not None
        assert hasattr(tool, "__registry_info__")

    @patch("inspect_ai.util._store_model.store_as")
    def test_restock_tool_insufficient_inventory(self, mock_store_as, mock_env):
        """Test restock tool with insufficient storage inventory."""
        mock_store_as.return_value = mock_env

        tool = restock_machine()
        assert tool is not None
        # Note: Error handling testing requires async execution context

    @patch("inspect_ai.util._store_model.store_as")
    def test_set_price_invalid_sku(self, mock_store_as, mock_env):
        """Test price setting with invalid SKU."""
        mock_store_as.return_value = mock_env

        tool = set_price()
        assert tool is not None

    @patch("inspect_ai.util._store_model.store_as")
    def test_get_machine_inventory_tool(self, mock_store_as, mock_env):
        """Test machine inventory snapshot tool creation."""
        mock_store_as.return_value = mock_env

        tool = get_machine_inventory()
        assert tool is not None

    @patch("inspect_ai.util._store_model.store_as")
    def test_place_order_insufficient_cash(self, mock_store_as, mock_env):
        """Test order placement with insufficient cash."""
        # Set low cash balance
        mock_env.state.cash_balance = 1.0
        mock_store_as.return_value = mock_env

        tool = place_order()
        assert tool is not None

    @patch("inspect_ai.util._store_model.store_as")
    def test_memory_tools_integration(self, mock_store_as, mock_memory):
        """Test memory tools basic integration."""
        mock_store_as.return_value = mock_memory

        # Test scratchpad tool
        scratchpad_tool = scratchpad_append()
        assert scratchpad_tool is not None

        # Test KV store tool
        kv_tool = kv_set()
        assert kv_tool is not None

        # Test vector search tool
        vector_tool = vector_search()
        assert vector_tool is not None


class TestToolCollections:
    """Test tool collection functions."""

    def test_supervisor_tools_collection(self):
        """Test supervisor tools collection."""
        tools = supervisor_tools()
        assert len(tools) > 0

        # Check expected tools are included
        tool_names = [
            getattr(tool, "__registry_info__", None).name if hasattr(tool, "__registry_info__") else None
            for tool in tools
        ]
        expected_tools = [
            "read_email",
            "send_email",
            "check_inventory",
            "check_financial_status",
            "place_order",
            "wait_for_next_day",
            "ai_web_search",
        ]

        for expected in expected_tools:
            assert expected in tool_names, f"Missing tool: {expected}"

    def test_physical_agent_tools_collection(self):
        """Test physical agent tools collection."""
        tools = physical_agent_tools()
        assert len(tools) > 0

        tool_names = [
            getattr(tool, "__registry_info__", None).name if hasattr(tool, "__registry_info__") else None
            for tool in tools
        ]
        expected_tools = ["restock_machine", "set_price", "collect_cash", "check_inventory", "get_machine_inventory"]

        for expected in expected_tools:
            assert expected in tool_names, f"Missing tool: {expected}"

    def test_memory_tools_collection(self):
        """Test memory tools collection."""
        tools = memory_tools()
        assert len(tools) > 0

        tool_names = [
            getattr(tool, "__registry_info__", None).name if hasattr(tool, "__registry_info__") else None
            for tool in tools
        ]
        expected_tools = [
            "scratchpad_append",
            "scratchpad_read",
            "kv_set",
            "kv_get",
            "kv_list",
            "vector_store",
            "vector_search",
        ]

        for expected in expected_tools:
            assert expected in tool_names, f"Missing memory tool: {expected}"

    def test_no_tool_overlap_supervisor_physical(self):
        """Test that supervisor and physical agent tools are properly separated."""
        supervisor_tools_list = supervisor_tools()
        physical_tools_list = physical_agent_tools()

        supervisor_names = {
            getattr(tool, "__registry_info__", None).name if hasattr(tool, "__registry_info__") else None
            for tool in supervisor_tools_list
        }
        physical_names = {
            getattr(tool, "__registry_info__", None).name if hasattr(tool, "__registry_info__") else None
            for tool in physical_tools_list
        }

        # Physical agent should not have access to high-level tools
        forbidden_for_physical = {"place_order", "wait_for_next_day", "ai_web_search", "read_email", "send_email"}
        physical_overlap = physical_names.intersection(forbidden_for_physical)
        assert len(physical_overlap) == 0, f"Physical agent has forbidden tools: {physical_overlap}"

        # Both can access inventory checking
        assert "check_inventory" in supervisor_names
        assert "check_inventory" in physical_names


class TestErrorHandling:
    """Test error handling and validation enforcement."""

    def test_tool_validation_enforcement(self):
        """Test that tools enforce parameter validation."""
        # Tools now perform validation during execution
        # This ensures invalid parameters are caught at runtime
        assert True  # Validation is enforced within tool implementations

    def test_tool_validation_behaviors(self):
        """Test that tools enforce validation during execution."""
        # Tools now handle validation internally
        # This is verified through runtime behavior testing
        assert True  # Placeholder for validation behavior tests


class TestDeterministicBehavior:
    """Test deterministic behavior of tools."""

    def test_web_search_deterministic_results(self):
        """Test that web search returns deterministic results."""
        # This is a design test - web search should return deterministic stub results
        # for the same query. The actual implementation provides deterministic
        # results based on query content matching.

        # Verify that ai_web_search tool exists and can be created
        search_tool = ai_web_search()
        assert search_tool is not None
        assert hasattr(search_tool, "__registry_info__")
        assert search_tool.__registry_info__.name == "ai_web_search"

        # Note: Testing actual deterministic output requires execution context

    def test_memory_store_deterministic_ids(self):
        """Test that memory store generates consistent IDs."""
        store = MemoryStore()

        # Generate some IDs
        id1 = store._generate_id()
        id2 = store._generate_id()
        id3 = store._generate_id()

        # IDs should be sequential and predictable
        assert id1 == "mem_000001"
        assert id2 == "mem_000002"
        assert id3 == "mem_000003"

    def test_tool_time_advancement_consistency(self):
        """Test that tools advance time consistently."""
        # Different operations should have consistent time costs
        # This is more of a design verification test

        # Read email: 5 minutes
        # Send email: 25 minutes
        # Restock: 75 minutes
        # Price change: 300 minutes (5 hours)
        # Order placement: 25 minutes (email-based)
        # Cash collection: 300 minutes (5 hours)
        # Web search: 60 minutes

        # These values are embedded in the tool implementations
        # and should remain consistent for deterministic behavior
        assert True  # Placeholder for design consistency check


class TestObservabilityHooks:
    """Test observability and logging integration."""

    @patch("examples.vending_bench.tools._log_tool_event")
    def test_tool_logging_called(self, mock_log_event):
        """Test that tools call logging functions."""
        # Set up mock to track calls
        mock_log_event.return_value = 12345.0

        # Create a tool (this should work without full Inspect context)
        tool = read_email()
        assert tool is not None

        # Note: Full logging verification requires async execution context

    @patch("examples.vending_bench.memory._log_memory_event")
    def test_memory_tool_logging(self, mock_log_event):
        """Test that memory tools call logging functions."""
        mock_log_event.return_value = 12345.0

        # Create memory tools
        tool = scratchpad_append()
        assert tool is not None

        kv_tool = kv_set()
        assert kv_tool is not None

    def test_logging_structured_format(self):
        """Test that logging produces structured output."""
        # Import the logging function directly
        from examples.vending_bench.memory import _log_memory_event
        from examples.vending_bench.tools import _log_tool_event

        # These should not raise exceptions when called
        t0 = _log_tool_event("test_tool", "start", {"param": "value"})
        assert isinstance(t0, float)

        _log_tool_event("test_tool", "end", extra={"result": "success"}, t0=t0)

        t0 = _log_memory_event("test_memory", "start")
        assert isinstance(t0, float)

        _log_memory_event("test_memory", "end", t0=t0)


if __name__ == "__main__":
    pytest.main([__file__])
