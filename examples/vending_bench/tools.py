"""Inspect-compliant tools for the vending bench environment.

This module wraps simulator operations as Inspect tools with Pydantic validation,
observability hooks, and error handling as specified in the design requirements.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

from .runtime import get_env, increment_tool_count
from .state import aggregate_sku_quantities, serialize_machine_inventory, MINUTES_PER_DAY, EmailMessage

if TYPE_CHECKING:
    from inspect_ai.tool._tool import Tool


class BaseToolParams(BaseModel):
    """Base class for tool parameters with common validation."""

    model_config = {"extra": "forbid"}  # Reject unknown fields as per design requirements


class ReadEmailResult(BaseModel):
    """Result from reading a single email."""

    inbox_remaining: int
    outbox_count: int
    message: dict[str, Any] | None


class SendEmailResult(BaseModel):
    """Result from sending an email."""

    recipient: str
    subject: str
    day: int
    outbox_count: int


class InventoryCheckResult(BaseModel):
    """Result from inventory check operation."""

    location: str
    inventory: dict[str, int]
    total_units: int
    slots: list[list[dict[str, Any] | None]] | None = None


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
    row: int
    column: int
    quantity_restocked: int
    slot_quantity: int
    slot_capacity: int
    remaining_storage: int


class SlotPriceUpdate(BaseModel):
    """Input payload describing a slot price update."""

    row: int
    column: int
    price: float


class SlotPriceUpdateResult(BaseModel):
    """Output payload for a slot price update."""

    row: int
    column: int
    sku: str
    old_price: float
    new_price: float


class SetPriceResult(BaseModel):
    """Result from price setting operation."""

    updates: list[SlotPriceUpdateResult]


class MachineInventorySlot(BaseModel):
    """Slot-level snapshot for machine inventory."""

    row: int
    column: int
    sku: str | None
    quantity: int
    price: float | None
    capacity: int | None


class MachineInventoryResult(BaseModel):
    """Structured slot-level machine inventory payload."""

    sku_totals: dict[str, int]
    total_units: int
    slots: list[MachineInventorySlot]


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


def _email_to_dict(message: EmailMessage, *, box: str) -> dict[str, Any]:
    """Convert an `EmailMessage` to a serialisable dictionary."""

    return {
        "day": message.day,
        "subject": message.subject,
        "body": message.body,
        "sender": message.sender,
        "recipient": message.recipient,
        "box": box,
    }


def read_email() -> Tool:
    """Read and remove the oldest email from the inbox."""

    from inspect_ai.tool._tool import tool

    @tool(name="read_email")
    def read_email_impl() -> ReadEmailResult:
        """Return the next inbox message, consuming it and costing five minutes."""

        t0 = _log_tool_event(name="read_email", phase="start")

        try:
            env = get_env()

            message_dict: dict[str, Any] | None = None
            if env.state.inbox:
                message = env.state.inbox.pop(0)
                message_dict = _email_to_dict(message, box="inbox")

            env.advance_time(5)

            result = ReadEmailResult(
                inbox_remaining=len(env.state.inbox),
                outbox_count=len(env.state.outbox),
                message=message_dict,
            )

            _log_tool_event(
                name="read_email",
                phase="end",
                extra={
                    "message_found": message_dict is not None,
                    "inbox_remaining": result.inbox_remaining,
                },
                t0=t0,
            )

            return result

        except Exception as e:
            _log_tool_event(name="read_email", phase="error", extra={"error": str(e)}, t0=t0)
            raise

    return read_email_impl


def send_email() -> Tool:
    """Send an email and record it in the outbox."""

    from inspect_ai.tool._tool import tool

    @tool(name="send_email")
    def send_email_impl(to: str, subject: str, body: str) -> SendEmailResult:
        """Send an email via the simulator, costing twenty-five minutes."""

        if not to:
            raise ValueError("recipient address must be provided")
        args = {"to": to, "subject": subject}
        t0 = _log_tool_event(name="send_email", phase="start", args=args)

        try:
            env = get_env()

            message = env.queue_email(recipient=to, subject=subject, body=body)

            env.advance_time(25)

            result = SendEmailResult(
                recipient=message.recipient,
                subject=message.subject,
                day=message.day,
                outbox_count=len(env.state.outbox),
            )

            _log_tool_event(
                name="send_email",
                phase="end",
                extra={"recipient": message.recipient, "outbox_count": result.outbox_count},
                t0=t0,
            )

            return result

        except Exception as e:
            _log_tool_event(name="send_email", phase="error", extra={"error": str(e)}, t0=t0)
            raise

    return send_email_impl


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
                slots = None
            else:  # machine
                inventory = aggregate_sku_quantities(env.state.machine_inventory)
                slots = serialize_machine_inventory(env.state.machine_inventory)

            total_units = sum(inventory.values())

            result = InventoryCheckResult(
                location=location,
                inventory=inventory,
                total_units=total_units,
                slots=slots,
            )

            _log_tool_event(
                name="check_inventory", phase="end", extra={"location": location, "total_units": total_units}, t0=t0
            )

            return result

        except Exception as e:
            _log_tool_event(name="check_inventory", phase="error", extra={"error": str(e)}, t0=t0)
            raise

    return check_inventory_impl


def get_machine_inventory() -> Tool:
    """Return slot-level machine inventory snapshot."""

    from inspect_ai.tool._tool import tool

    @tool(name="get_machine_inventory")
    def get_machine_inventory_impl() -> MachineInventoryResult:
        t0 = _log_tool_event(name="get_machine_inventory", phase="start", args={})

        try:
            env = get_env()
            totals = aggregate_sku_quantities(env.state.machine_inventory)
            slots: list[MachineInventorySlot] = []
            for row_idx, row in enumerate(env.state.machine_inventory):
                for col_idx, slot in enumerate(row):
                    slots.append(
                        MachineInventorySlot(
                            row=row_idx,
                            column=col_idx,
                            sku=slot.sku if slot else None,
                            quantity=slot.quantity if slot else 0,
                            price=slot.price if slot else None,
                            capacity=slot.capacity if slot else None,
                        )
                    )

            total_units = sum(totals.values())
            result = MachineInventoryResult(sku_totals=totals, total_units=total_units, slots=slots)

            _log_tool_event(
                name="get_machine_inventory",
                phase="end",
                extra={"total_units": total_units, "slot_count": len(slots)},
                t0=t0,
            )

            return result

        except Exception as e:
            _log_tool_event(name="get_machine_inventory", phase="error", extra={"error": str(e)}, t0=t0)
            raise

    return get_machine_inventory_impl


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

    from inspect_agents.exceptions import ToolException

    @tool(name="restock_machine")
    def restock_machine_impl(sku: str, quantity: int, row: int, column: int) -> RestockMachineResult:
        """Restock vending machine from storage inventory.

        Args:
            sku: Product SKU to restock
            quantity: Number of units to restock
            row: Target machine row (0-indexed)
            column: Target machine column (0-indexed)
        """

        if quantity <= 0:
            raise ValueError("quantity must be positive")

        t0 = _log_tool_event(
            name="restock_machine",
            phase="start",
            args={"sku": sku, "quantity": quantity, "row": row, "column": column},
        )

        try:
            env = get_env()

            # Check storage availability before restocking
            available = env.state.storage_inventory.get(sku, 0)
            if available < quantity:
                raise ToolException(f"Insufficient storage inventory for {sku}: have {available}, need {quantity}")

            env.restock(sku, quantity, row=row, column=column)
            env.advance_time(75)  # 75 minutes per benchmark specification

            slot = env.state.machine_inventory[row][column]
            if slot is None:
                raise ToolException(f"slot ({row}, {column}) unavailable after restock")
            capacity = (
                slot.capacity
                if slot and slot.capacity is not None
                else env.state.demand_profiles[sku].product.slot_capacity
            )

            result = RestockMachineResult(
                sku=sku,
                row=row,
                column=column,
                quantity_restocked=quantity,
                slot_quantity=slot.quantity if slot else 0,
                slot_capacity=capacity,
                remaining_storage=env.state.storage_inventory.get(sku, 0),
            )

            _log_tool_event(
                name="restock_machine",
                phase="end",
                extra={
                    "sku": sku,
                    "quantity": quantity,
                    "row": row,
                    "column": column,
                    "slot_quantity": result.slot_quantity,
                },
                t0=t0,
            )

            return result

        except Exception as e:
            _log_tool_event(
                name="restock_machine",
                phase="error",
                extra={"error": str(e), "sku": sku, "row": row, "column": column},
                t0=t0,
            )
            if isinstance(e, ToolException):
                raise
            raise ToolException(f"Restock failed: {str(e)}")

    return restock_machine_impl


def set_price() -> Tool:
    """Set the price for a product."""

    from inspect_ai.tool._tool import tool

    from inspect_agents.exceptions import ToolException

    @tool(name="set_price")
    def set_price_impl(updates: list[SlotPriceUpdate]) -> SetPriceResult:
        """Set selling prices for machine slots.

        Args:
            updates: List of slot updates with row, column, and target price
        """

        if not updates:
            raise ValueError("updates must not be empty")

        for update in updates:
            if update.price <= 0:
                raise ValueError("price must be positive")

        t0 = _log_tool_event(
            name="set_price",
            phase="start",
            args={
                "updates": [update.model_dump() for update in updates],
            },
        )

        try:
            env = get_env()

            snapshot: dict[tuple[int, int], tuple[str, float]] = {}
            for update in updates:
                slot = env.state.machine_inventory[update.row][update.column]
                if slot is None or slot.sku is None:
                    raise ToolException(f"slot ({update.row}, {update.column}) is empty")
                product = env.state.demand_profiles[slot.sku].product
                old_price = slot.price if slot.price is not None else product.base_price
                snapshot[(update.row, update.column)] = (slot.sku, old_price)

            env.set_price({(upd.row, upd.column): upd.price for upd in updates})
            env.advance_time(300)  # 5 hours for price changes

            results = [
                SlotPriceUpdateResult(
                    row=upd.row,
                    column=upd.column,
                    sku=snapshot[(upd.row, upd.column)][0],
                    old_price=snapshot[(upd.row, upd.column)][1],
                    new_price=upd.price,
                )
                for upd in updates
            ]

            result = SetPriceResult(updates=results)

            _log_tool_event(
                name="set_price",
                phase="end",
                extra={
                    "updated_slots": [
                        {
                            "row": upd.row,
                            "column": upd.column,
                            "new_price": upd.price,
                        }
                        for upd in updates
                    ]
                },
                t0=t0,
            )

            return result

        except Exception as e:
            _log_tool_event(
                name="set_price",
                phase="error",
                extra={"error": str(e), "updates": [upd.model_dump() for upd in updates]},
                t0=t0,
            )
            if isinstance(e, ToolException):
                raise
            raise ToolException(f"Price setting failed: {str(e)}")

    return set_price_impl


def place_order() -> Tool:
    """Place an order with suppliers for inventory."""

    from inspect_ai.tool._tool import tool

    from inspect_agents.exceptions import ToolException

    @tool(name="place_order")
    def place_order_impl(sku: str, quantity: int) -> PlaceOrderResult:
        """Place supplier order for inventory with automatic cost deduction.

        Args:
            sku: Product SKU to order
            quantity: Number of units to order
        """

        if quantity <= 0:
            raise ValueError("quantity must be positive")

        t0 = _log_tool_event(name="place_order", phase="start", args={"sku": sku, "quantity": quantity})

        try:
            env = get_env()

            order = env.place_order(sku, quantity)
            env.advance_time(25)  # 25 minutes to compose and send the supplier email

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
            _log_tool_event(name="place_order", phase="error", extra={"error": str(e), "sku": sku}, t0=t0)
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
            env.advance_time(300)  # 5 hours for cash collection

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
            current_minute = env.state.minute
            minutes_remaining = MINUTES_PER_DAY - current_minute if current_minute > 0 else MINUTES_PER_DAY

            env.advance_time(minutes_remaining)
            env.state.minute = 0

            latest_report = env.latest_report()
            report_dict = {}
            if latest_report:
                report_dict = {
                    "day": latest_report.day,
                    "revenue": latest_report.revenue,
                    "cash_balance": latest_report.cash_balance,
                    "cash_in_machine": latest_report.cash_in_machine,
                    "storage_inventory": latest_report.storage_inventory,
                    "machine_inventory": serialize_machine_inventory(latest_report.machine_inventory),
                    "machine_inventory_totals": aggregate_sku_quantities(latest_report.machine_inventory),
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
        read_email(),
        send_email(),
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
        get_machine_inventory(),
    ]


def all_vending_tools() -> list[Tool]:
    """Return all vending bench tools for testing purposes."""
    return [
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
