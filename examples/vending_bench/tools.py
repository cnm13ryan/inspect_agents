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
from .state import MINUTES_PER_DAY, EmailMessage, aggregate_sku_quantities, serialize_machine_inventory

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


class MachineInventoryOverviewResult(BaseModel):
    """Summarised view of machine inventory for supervisors."""

    total_units: int
    unique_skus: int
    sku_totals: dict[str, int]
    low_stock_skus: list[dict[str, int]]


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


def _inventory_snapshot(location: str) -> tuple[dict[str, int], int]:
    """Return a copy of inventory and total units for a given location."""

    env = get_env()

    if location == "storage":
        inventory = dict(env.state.storage_inventory)
    elif location == "machine":
        inventory = aggregate_sku_quantities(env.state.machine_inventory)
    else:
        raise ValueError("location must be 'storage' or 'machine'")

    total_units = sum(inventory.values())

    return inventory, total_units


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
            inventory, total_units = _inventory_snapshot(location)
            env = get_env()

            if location == "storage":
                slots = None
            else:  # machine
                slots = serialize_machine_inventory(env.state.machine_inventory)

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


def check_storage_inventory() -> Tool:
    """Supervisor wrapper for storage inventory details."""

    from inspect_ai.tool._tool import tool

    @tool(name="check_storage_inventory")
    def check_storage_inventory_impl() -> InventoryCheckResult:
        """Return storage inventory using the underlying inventory snapshot."""

        t0 = _log_tool_event(name="check_storage_inventory", phase="start")

        try:
            inventory, total_units = _inventory_snapshot("storage")

            result = InventoryCheckResult(location="storage", inventory=inventory, total_units=total_units)

            _log_tool_event(name="check_storage_inventory", phase="end", extra={"total_units": total_units}, t0=t0)

            return result

        except Exception as e:
            _log_tool_event(name="check_storage_inventory", phase="error", extra={"error": str(e)}, t0=t0)
            raise

    return check_storage_inventory_impl


def check_machine_overview() -> Tool:
    """Supervisor wrapper exposing summarised machine inventory data."""

    from inspect_ai.tool._tool import tool

    @tool(name="check_machine_overview")
    def check_machine_overview_impl(low_stock_threshold: int = 5) -> MachineInventoryOverviewResult:
        """Provide aggregated machine inventory totals without slot-level detail.

        Args:
            low_stock_threshold: Units at or below which SKUs are considered low stock.
        """

        if low_stock_threshold < 0:
            raise ValueError("low_stock_threshold must be non-negative")

        t0 = _log_tool_event(
            name="check_machine_overview", phase="start", args={"low_stock_threshold": low_stock_threshold}
        )

        try:
            inventory, total_units = _inventory_snapshot("machine")
            unique_skus = len(inventory)

            low_stock_skus = [
                {"sku": sku, "units": units}
                for sku, units in sorted(inventory.items(), key=lambda item: item[1])
                if units <= low_stock_threshold
            ]

            result = MachineInventoryOverviewResult(
                total_units=total_units,
                unique_skus=unique_skus,
                sku_totals=inventory,
                low_stock_skus=low_stock_skus,
            )

            _log_tool_event(
                name="check_machine_overview",
                phase="end",
                extra={
                    "total_units": total_units,
                    "unique_skus": unique_skus,
                    "low_stock_count": len(low_stock_skus),
                },
                t0=t0,
            )

            return result

        except Exception as e:
            _log_tool_event(name="check_machine_overview", phase="error", extra={"error": str(e)}, t0=t0)
            raise

    return check_machine_overview_impl


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

    @tool(name="restock_machine")
    def restock_machine_impl(
        sku: str | None = None, quantity: int | None = None, row: int | None = None, column: int | None = None
    ) -> RestockMachineResult:
        """Restock vending machine from storage inventory.

        Args:
            sku: Product SKU to restock
            quantity: Number of units to restock
            row: Target machine row (0-indexed)
            column: Target machine column (0-indexed)
        """

        validated_sku = _require_non_empty_string("sku", sku)
        validated_quantity = _require_positive_int("quantity", quantity)
        validated_row = _require_positive_int("row", row) if row is not None else _require_positive_int("row", None)
        validated_column = (
            _require_positive_int("column", column) if column is not None else _require_positive_int("column", None)
        )

        t0 = _log_tool_event(
            name="restock_machine",
            phase="start",
            args={
                "sku": validated_sku,
                "quantity": validated_quantity,
                "row": validated_row,
                "column": validated_column,
            },
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

            # Convert 1-indexed input to 0-indexed for environment
            env_row = validated_row - 1
            env_column = validated_column - 1

            env.restock(validated_sku, validated_quantity, row=env_row, column=env_column)
            env.advance_time(75)  # 75 minutes per benchmark specification

            slot = env.state.machine_inventory[env_row][env_column]
            if slot is None:
                raise ToolException(f"slot ({validated_row}, {validated_column}) unavailable after restock")
            capacity = (
                slot.capacity
                if slot and slot.capacity is not None
                else env.state.demand_profiles[validated_sku].product.slot_capacity
            )

            result = RestockMachineResult(
                sku=validated_sku,
                row=validated_row,
                column=validated_column,
                quantity_restocked=validated_quantity,
                slot_quantity=slot.quantity if slot else 0,
                slot_capacity=capacity,
                remaining_storage=env.state.storage_inventory.get(validated_sku, 0),
            )

            _log_tool_event(
                name="restock_machine",
                phase="end",
                extra={
                    "sku": validated_sku,
                    "quantity": validated_quantity,
                    "row": validated_row,
                    "column": validated_column,
                    "slot_quantity": result.slot_quantity,
                },
                t0=t0,
            )

            return result

        except Exception as e:
            _log_tool_event(
                name="restock_machine",
                phase="error",
                extra={"error": str(e), "sku": validated_sku, "row": validated_row, "column": validated_column},
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
                # Convert 1-indexed input to 0-indexed for environment
                env_row = update.row - 1
                env_column = update.column - 1
                slot = env.state.machine_inventory[env_row][env_column]
                if slot is None or slot.sku is None:
                    raise ToolException(f"slot ({update.row}, {update.column}) is empty")
                profile = env.state.demand_profiles[slot.sku]
                fallback_price = (
                    profile.reference_price if profile.reference_price is not None else profile.product.base_price
                )
                old_price = slot.price if slot.price is not None else fallback_price
                snapshot[(update.row, update.column)] = (slot.sku, old_price)

            env.set_price({(upd.row - 1, upd.column - 1): upd.price for upd in updates})
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

            # Enhanced deterministic supplier search results with dynamic content based on catalog
            stub_results: list[dict[str, Any]] = []
            normalized_query = query.lower()

            # Get available SKUs from environment catalog
            available_skus = set(env.state.demand_profiles.keys())

            if any(term in normalized_query for term in ("supplier", "vendor", "wholesale", "contact")):
                # Build dynamic supplier results based on available catalog
                suppliers_data = [
                    {
                        "name": "Regional Food Distributors Inc.",
                        "email": "orders@rfd-inc.com",
                        "phone": "+1-800-555-0110",
                        "url": "https://example-supplier1.com",
                        "snippet": "Bulk beverage catalogue with predictable 2-5 day delivery windows across the Midwest.",
                        "categories": ["beverage"],
                        "specialties": ["coke", "water", "energy_drink"],
                        "min_orders": {"coke": 24, "water": 24, "energy_drink": 12},
                        "price_multiplier": 0.95,
                        "lead_time": "2-5"
                    },
                    {
                        "name": "QuickStock Vending Solutions",
                        "email": "supply@quickstock.com",
                        "phone": "+1-800-555-0148",
                        "url": "https://example-supplier2.com",
                        "snippet": "Fast-turn snack distributor with local cross-dock for 1-3 day replenishment.",
                        "categories": ["snack", "impulse"],
                        "specialties": ["chips", "chocolate_bar", "energy_drink"],
                        "min_orders": {"chips": 12, "chocolate_bar": 12, "energy_drink": 12},
                        "price_multiplier": 0.90,
                        "lead_time": "1-3"
                    },
                    {
                        "name": "Metro Wholesale Foods",
                        "email": "sales@metrofoods.example",
                        "phone": "+1-800-555-0190",
                        "url": "https://example-supplier3.com",
                        "snippet": "Balanced assortment for office routes with 3-6 day scheduled deliveries.",
                        "categories": ["balanced", "office"],
                        "specialties": list(available_skus),
                        "min_orders": {sku: 18 for sku in available_skus},
                        "price_multiplier": 1.0,
                        "lead_time": "3-6"
                    }
                ]

                for supplier in suppliers_data:
                    # Build catalog for available SKUs
                    catalog = []
                    for sku in supplier["specialties"]:
                        if sku in available_skus:
                            profile = env.state.demand_profiles[sku]
                            wholesale_price = profile.product.unit_cost * supplier["price_multiplier"]
                            catalog.append({
                                "sku": sku,
                                "name": profile.product.name,
                                "category": "beverage" if "beverage" in supplier["categories"] else profile.product.variety_class.lower(),
                                "min_order": supplier["min_orders"].get(sku, 18),
                                "wholesale_price": round(wholesale_price, 2),
                                "lead_time_days": supplier["lead_time"]
                            })

                    if catalog:  # Only include suppliers with available products
                        stub_results.append({
                            "title": supplier["name"],
                            "url": supplier["url"],
                            "snippet": supplier["snippet"],
                            "contact": {"email": supplier["email"], "phone": supplier["phone"]},
                            "categories": supplier["categories"],
                            "catalog": catalog
                        })
            elif any(term in normalized_query for term in ("product list", "snack", "catalogue", "pricing")):
                stub_results = [
                    {
                        "title": "Top vending machine performers",
                        "url": "https://example-market-research.com",
                        "snippet": "Chilled beverages and grab-and-go snacks drive 68% of office vending revenue.",
                        "data": {
                            "beverage": {"top_skus": ["coke", "water", "energy_drink"], "avg_wholesale": 0.60},
                            "snack": {"top_skus": ["chips", "chocolate_bar"], "avg_wholesale": 0.62},
                        },
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
        check_storage_inventory(),
        check_machine_overview(),
        read_email(),
        send_email(),
        check_financial_status(),
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
        check_storage_inventory(),
        check_machine_overview(),
        check_financial_status(),
        restock_machine(),
        set_price(),
        collect_cash(),
        wait_for_next_day(),
        ai_web_search(),
        get_machine_inventory(),
    ]
