"""Inspect-compliant tools for the vending bench environment.

This module wraps simulator operations as Inspect tools with Pydantic validation,
observability hooks, and error handling as specified in the design requirements.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

from inspect_agents.exceptions import ToolException

from .runtime import get_env, increment_tool_count

if TYPE_CHECKING:
    from inspect_ai.tool._tool import Tool


class BaseToolParams(BaseModel):
    """Base class for tool parameters with common validation."""

    model_config = {"extra": "forbid"}  # Reject unknown fields as per design requirements


class EmailCheckResult(BaseModel):
    """Result from email check operation."""

    inbox_count: int
    outbox_count: int
    messages: list[dict[str, Any]]


class InventoryCheckResult(BaseModel):
    """Result from inventory check operation."""

    location: str
    inventory: dict[str, int]
    total_units: int


class FinancialStatusResult(BaseModel):
    """Result from financial status check."""

    cash_balance: float
    cash_in_machine: float
    net_worth: float
    daily_fee: float
    bankruptcy_risk: bool


class RestockMachineResult(BaseModel):
    """Result from restock operation."""

    sku: str
    quantity_restocked: int
    new_machine_inventory: int
    remaining_storage: int


class SetPriceResult(BaseModel):
    """Result from price setting operation."""

    sku: str
    old_price: float
    new_price: float


class PlaceOrderResult(BaseModel):
    """Result from order placement."""

    order_id: str
    sku: str
    quantity: int
    total_cost: float
    delivery_day: int


class CollectCashResult(BaseModel):
    """Result from cash collection."""

    amount_collected: float
    new_balance: float


class WaitForNextDayResult(BaseModel):
    """Result from day advancement."""

    new_day: int
    daily_report: dict[str, Any]


class WebSearchResult(BaseModel):
    """Result from web search (deterministic stub)."""

    query: str
    results: list[dict[str, Any]]


def _require_non_empty_string(name: str, value: str | None) -> str:
    """Ensure a string parameter is provided."""

    if value is None:
        raise ToolException(f"{name} is required to complete this action. Please provide the {name}.")

    sanitized = value.strip()
    if not sanitized:
        raise ToolException(f"{name} cannot be empty. Please provide a specific {name}.")

    return sanitized


def _require_positive_int(name: str, value: int | None) -> int:
    """Ensure an integer parameter is positive."""

    if value is None:
        raise ToolException(f"{name} is required to complete this action. Please provide the {name}.")

    if isinstance(value, bool):  # bool is a subclass of int; do not accept
        raise ToolException(f"{name} must be a whole number greater than zero. Please provide a positive integer.")

    if not isinstance(value, int):
        raise ToolException(f"{name} must be a whole number greater than zero. Please provide a positive integer.")

    if value <= 0:
        raise ToolException(f"{name} must be greater than zero. Please provide a positive value for {name}.")

    return value


def _require_positive_float(name: str, value: float | int | None) -> float:
    """Ensure a numeric parameter is a positive float."""

    if value is None:
        raise ToolException(f"{name} is required to complete this action. Please provide the {name}.")

    if isinstance(value, bool):
        raise ToolException(f"{name} must be a positive number. Please provide a numeric value greater than zero.")

    try:
        numeric = float(value)
    except (TypeError, ValueError):
        raise ToolException(f"{name} must be a positive number. Please provide a numeric value greater than zero.")

    if numeric <= 0:
        raise ToolException(f"{name} must be greater than zero. Please provide a positive value for {name}.")

    return numeric


def _require_known_sku(env: Any, sku: str) -> None:
    """Ensure the SKU exists in the environment catalog."""

    demand_profiles = getattr(env.state, "demand_profiles", {})
    if sku not in demand_profiles:
        known_skus = sorted(demand_profiles.keys())
        preview = ", ".join(known_skus[:5]) if known_skus else "no registered SKUs"
        raise ToolException(
            f"Unknown SKU '{sku}'. Please choose a valid SKU from the machine inventory (e.g., {preview})."
        )


def _log_tool_event(
    name: str,
    phase: str,
    args: dict[str, Any] | None = None,
    extra: dict[str, Any] | None = None,
    t0: float | None = None,
) -> float:
    """Log tool events for observability."""
    import time

    if t0 is None:
        t0 = time.time()

    logger = logging.getLogger(__name__)
    log_data = {
        "tool": name,
        "phase": phase,
        "timestamp": time.time(),
    }

    if args:
        log_data["args"] = args
    if extra:
        log_data["extra"] = extra
    if phase == "end" and t0:
        log_data["duration_ms"] = (time.time() - t0) * 1000

    if phase == "start":
        increment_tool_count(name)

    logger.info(f"Tool event: {json.dumps(log_data)}")
    return t0 if phase == "start" else time.time()


def check_email() -> Tool:
    """Check inbox and outbox for new emails."""

    from inspect_ai.tool._tool import tool

    @tool(name="check_email")
    def check_email_impl(max_emails: int = 10) -> EmailCheckResult:
        """Check inbox and outbox for emails with daily summaries and order confirmations.

        Args:
            max_emails: Maximum number of emails to retrieve from each box
        """

        t0 = _log_tool_event(name="check_email", phase="start", args={"max_emails": max_emails})

        try:
            # Get environment from store
            env = get_env()

            inbox_messages = []
            for msg in env.state.inbox[-max_emails:]:
                inbox_messages.append(
                    {
                        "day": msg.day,
                        "subject": msg.subject,
                        "body": msg.body,
                        "sender": msg.sender,
                        "recipient": msg.recipient,
                        "type": "inbox",
                    }
                )

            outbox_messages = []
            for msg in env.state.outbox[-max_emails:]:
                outbox_messages.append(
                    {
                        "day": msg.day,
                        "subject": msg.subject,
                        "body": msg.body,
                        "sender": msg.sender,
                        "recipient": msg.recipient,
                        "type": "outbox",
                    }
                )

            all_messages = inbox_messages + outbox_messages
            all_messages.sort(key=lambda x: x["day"], reverse=True)

            result = EmailCheckResult(
                inbox_count=len(env.state.inbox), outbox_count=len(env.state.outbox), messages=all_messages[:max_emails]
            )

            _log_tool_event(
                name="check_email",
                phase="end",
                extra={"inbox_count": result.inbox_count, "outbox_count": result.outbox_count},
                t0=t0,
            )

            return result

        except Exception as e:
            _log_tool_event(name="check_email", phase="error", extra={"error": str(e)}, t0=t0)
            raise

    return check_email_impl


def check_inventory() -> Tool:
    """Check storage or machine inventory levels."""

    from inspect_ai.tool._tool import tool

    @tool(name="check_inventory")
    def check_inventory_impl(location: str) -> InventoryCheckResult:
        """Check current inventory levels in storage or vending machine.

        Args:
            location: Either 'storage' or 'machine' to specify which inventory to check
        """

        if location not in ["storage", "machine"]:
            raise ValueError("location must be 'storage' or 'machine'")

        t0 = _log_tool_event(name="check_inventory", phase="start", args={"location": location})

        try:
            env = get_env()

            if location == "storage":
                inventory = dict(env.state.storage_inventory)
            else:  # machine
                inventory = dict(env.state.machine_inventory)

            total_units = sum(inventory.values())

            result = InventoryCheckResult(location=location, inventory=inventory, total_units=total_units)

            _log_tool_event(
                name="check_inventory", phase="end", extra={"location": location, "total_units": total_units}, t0=t0
            )

            return result

        except Exception as e:
            _log_tool_event(name="check_inventory", phase="error", extra={"error": str(e)}, t0=t0)
            raise

    return check_inventory_impl


def check_financial_status() -> Tool:
    """Check current financial status including cash and net worth."""

    from inspect_ai.tool._tool import tool

    @tool(name="check_financial_status")
    def check_financial_status_impl(include_projections: bool = False) -> FinancialStatusResult:
        """Check current cash balance, net worth, and bankruptcy risk.

        Args:
            include_projections: Whether to include financial projections in the result
        """

        t0 = _log_tool_event(
            name="check_financial_status", phase="start", args={"include_projections": include_projections}
        )

        try:
            env = get_env()
            summary = env.summary()

            # Check bankruptcy risk (less than 2 days of fees)
            bankruptcy_risk = summary.cash_balance < (env.config.daily_fee * 2)

            result = FinancialStatusResult(
                cash_balance=summary.cash_balance,
                cash_in_machine=summary.cash_in_machine,
                net_worth=summary.net_worth,
                daily_fee=env.config.daily_fee,
                bankruptcy_risk=bankruptcy_risk,
            )

            _log_tool_event(
                name="check_financial_status",
                phase="end",
                extra={"net_worth": result.net_worth, "bankruptcy_risk": bankruptcy_risk},
                t0=t0,
            )

            return result

        except Exception as e:
            _log_tool_event(name="check_financial_status", phase="error", extra={"error": str(e)}, t0=t0)
            raise

    return check_financial_status_impl


def restock_machine() -> Tool:
    """Restock vending machine from storage inventory."""

    from inspect_ai.tool._tool import tool

    @tool(name="restock_machine")
    def restock_machine_impl(sku: str | None = None, quantity: int | None = None) -> RestockMachineResult:
        """Restock vending machine from storage inventory.

        Args:
            sku: Product SKU to restock
            quantity: Number of units to restock
        """

        validated_sku = _require_non_empty_string("sku", sku)
        validated_quantity = _require_positive_int("quantity", quantity)

        t0 = _log_tool_event(
            name="restock_machine",
            phase="start",
            args={"sku": validated_sku, "quantity": validated_quantity},
        )

        try:
            env = get_env()

            _require_known_sku(env, validated_sku)

            # Check storage availability before restocking
            available = env.state.storage_inventory.get(validated_sku, 0)
            if available < validated_quantity:
                raise ToolException(
                    f"Insufficient storage inventory for {validated_sku}: have {available}, need {validated_quantity}"
                )

            env.restock(validated_sku, validated_quantity)
            env.advance_time(15)  # 15 minutes for restocking

            result = RestockMachineResult(
                sku=validated_sku,
                quantity_restocked=validated_quantity,
                new_machine_inventory=env.state.machine_inventory.get(validated_sku, 0),
                remaining_storage=env.state.storage_inventory.get(validated_sku, 0),
            )

            _log_tool_event(
                name="restock_machine",
                phase="end",
                extra={
                    "sku": validated_sku,
                    "quantity": validated_quantity,
                    "new_machine_inventory": result.new_machine_inventory,
                },
                t0=t0,
            )

            return result

        except Exception as e:
            _log_tool_event(
                name="restock_machine",
                phase="error",
                extra={"error": str(e), "sku": validated_sku},
                t0=t0,
            )
            if isinstance(e, ToolException):
                raise
            raise ToolException(f"Restock failed: {str(e)}")

    return restock_machine_impl


def set_price() -> Tool:
    """Set the price for a product."""

    from inspect_ai.tool._tool import tool

    @tool(name="set_price")
    def set_price_impl(sku: str | None = None, price: float | int | None = None) -> SetPriceResult:
        """Set the selling price for a product.

        Args:
            sku: Product SKU to update
            price: New selling price (must be positive)
        """

        validated_sku = _require_non_empty_string("sku", sku)
        validated_price = _require_positive_float("price", price)

        t0 = _log_tool_event(
            name="set_price",
            phase="start",
            args={"sku": validated_sku, "price": validated_price},
        )

        try:
            env = get_env()

            _require_known_sku(env, validated_sku)

            # Get old price
            old_price = env.state.prices.get(validated_sku, env.state.demand_profiles[validated_sku].product.base_price)

            env.set_price(validated_sku, validated_price)
            env.advance_time(5)  # 5 minutes for price change

            result = SetPriceResult(sku=validated_sku, old_price=old_price, new_price=validated_price)

            _log_tool_event(
                name="set_price",
                phase="end",
                extra={"sku": validated_sku, "old_price": old_price, "new_price": validated_price},
                t0=t0,
            )

            return result

        except Exception as e:
            _log_tool_event(
                name="set_price",
                phase="error",
                extra={"error": str(e), "sku": validated_sku},
                t0=t0,
            )
            if isinstance(e, ToolException):
                raise
            raise ToolException(f"Price setting failed: {str(e)}")

    return set_price_impl


def place_order() -> Tool:
    """Place an order with suppliers for inventory."""

    from inspect_ai.tool._tool import tool

    @tool(name="place_order")
    def place_order_impl(sku: str | None = None, quantity: int | None = None) -> PlaceOrderResult:
        """Place supplier order for inventory with automatic cost deduction.

        Args:
            sku: Product SKU to order
            quantity: Number of units to order
        """

        validated_sku = _require_non_empty_string("sku", sku)
        validated_quantity = _require_positive_int("quantity", quantity)

        t0 = _log_tool_event(
            name="place_order",
            phase="start",
            args={"sku": validated_sku, "quantity": validated_quantity},
        )

        try:
            env = get_env()

            _require_known_sku(env, validated_sku)

            order = env.place_order(validated_sku, validated_quantity)
            env.advance_time(30)  # 30 minutes for order processing

            result = PlaceOrderResult(
                order_id=f"{order.sku}_{order.day_ordered}_{len(env.state.outstanding_orders)}",
                sku=order.sku,
                quantity=order.quantity,
                total_cost=order.total_cost,
                delivery_day=order.delivery_day,
            )

            _log_tool_event(
                name="place_order",
                phase="end",
                extra={
                    "sku": order.sku,
                    "quantity": order.quantity,
                    "total_cost": order.total_cost,
                    "delivery_day": order.delivery_day,
                },
                t0=t0,
            )

            return result

        except Exception as e:
            _log_tool_event(
                name="place_order",
                phase="error",
                extra={"error": str(e), "sku": validated_sku},
                t0=t0,
            )
            if isinstance(e, ToolException):
                raise
            raise ToolException(f"Order placement failed: {str(e)}")

    return place_order_impl


def collect_cash() -> Tool:
    """Collect cash from the vending machine."""

    from inspect_ai.tool._tool import tool

    @tool(name="collect_cash")
    def collect_cash_impl() -> CollectCashResult:
        """Collect all cash from the vending machine."""

        t0 = _log_tool_event(name="collect_cash", phase="start")

        try:
            env = get_env()

            amount_collected = env.collect_machine_cash()
            env.advance_time(10)  # 10 minutes for cash collection

            result = CollectCashResult(amount_collected=amount_collected, new_balance=env.state.cash_balance)

            _log_tool_event(
                name="collect_cash",
                phase="end",
                extra={"amount_collected": amount_collected, "new_balance": result.new_balance},
                t0=t0,
            )

            return result

        except Exception as e:
            _log_tool_event(name="collect_cash", phase="error", extra={"error": str(e)}, t0=t0)
            raise

    return collect_cash_impl


def wait_for_next_day() -> Tool:
    """Advance to the next day and get daily report."""

    from inspect_ai.tool._tool import tool

    @tool(name="wait_for_next_day")
    def wait_for_next_day_impl() -> WaitForNextDayResult:
        """Advance to next day and receive daily report with sales and deliveries."""

        t0 = _log_tool_event(name="wait_for_next_day", phase="start")

        try:
            env = get_env()

            old_day = env.state.day
            env.end_of_day()

            latest_report = env.latest_report()
            report_dict = {}
            if latest_report:
                report_dict = {
                    "day": latest_report.day,
                    "revenue": latest_report.revenue,
                    "cash_balance": latest_report.cash_balance,
                    "cash_in_machine": latest_report.cash_in_machine,
                    "storage_inventory": latest_report.storage_inventory,
                    "machine_inventory": latest_report.machine_inventory,
                    "units_sold": latest_report.units_sold,
                    "deliveries": latest_report.deliveries,
                }

            result = WaitForNextDayResult(new_day=env.state.day, daily_report=report_dict)

            _log_tool_event(
                name="wait_for_next_day",
                phase="end",
                extra={"old_day": old_day, "new_day": env.state.day, "revenue": report_dict.get("revenue", 0)},
                t0=t0,
            )

            return result

        except Exception as e:
            _log_tool_event(name="wait_for_next_day", phase="error", extra={"error": str(e)}, t0=t0)
            raise

    return wait_for_next_day_impl


def ai_web_search() -> Tool:
    """Perform web search for supplier information (deterministic stub)."""

    from inspect_ai.tool._tool import tool

    @tool(name="ai_web_search")
    def ai_web_search_impl(query: str, max_results: int = 5) -> WebSearchResult:
        """Search for supplier contacts and product information (deterministic results).

        Args:
            query: Search query string
            max_results: Maximum number of search results to return
        """

        if max_results < 1 or max_results > 20:
            raise ValueError("max_results must be between 1 and 20")

        t0 = _log_tool_event(name="ai_web_search", phase="start", args={"query": query, "max_results": max_results})

        try:
            env = get_env()
            env.advance_time(60)  # 1 hour for research

            # Deterministic stub results based on query content
            stub_results = []
            if "supplier" in query.lower() or "vendor" in query.lower():
                stub_results = [
                    {
                        "title": "Regional Food Distributors Inc.",
                        "url": "https://example-supplier1.com",
                        "snippet": "Bulk snack and beverage supplier with 2-5 day lead times. Competitive pricing on popular vending items.",
                        "contact": "orders@rfd-inc.com",
                    },
                    {
                        "title": "QuickStock Vending Solutions",
                        "url": "https://example-supplier2.com",
                        "snippet": "Specialized vending machine inventory supplier. Same-day delivery available for local area.",
                        "contact": "supply@quickstock.com",
                    },
                ]
            elif "product" in query.lower() or "snack" in query.lower():
                stub_results = [
                    {
                        "title": "Popular Vending Machine Snacks 2024",
                        "url": "https://example-market-research.com",
                        "snippet": "Analysis of top-selling vending items. Chips, candy, and energy drinks lead sales.",
                        "data": "market_trends",
                    }
                ]

            result = WebSearchResult(query=query, results=stub_results[:max_results])

            _log_tool_event(
                name="ai_web_search", phase="end", extra={"query": query, "results_count": len(result.results)}, t0=t0
            )

            return result

        except Exception as e:
            _log_tool_event(name="ai_web_search", phase="error", extra={"error": str(e)}, t0=t0)
            raise

    return ai_web_search_impl


def supervisor_tools() -> list[Tool]:
    """Return list of tools available to the supervisor agent."""
    return [
        check_email(),
        check_inventory(),
        check_financial_status(),
        place_order(),
        wait_for_next_day(),
        ai_web_search(),
    ]


def physical_agent_tools() -> list[Tool]:
    """Return list of tools available to the physical sub-agent."""
    return [
        restock_machine(),
        set_price(),
        collect_cash(),
        check_inventory(),
    ]


def all_vending_tools() -> list[Tool]:
    """Return all vending bench tools for testing purposes."""
    return [
        check_email(),
        check_inventory(),
        check_financial_status(),
        restock_machine(),
        set_price(),
        place_order(),
        collect_cash(),
        wait_for_next_day(),
        ai_web_search(),
    ]
