from __future__ import annotations

from collections import defaultdict
from typing import Any

from wealth_advisor.schemas.client import ClientProfile
from wealth_advisor.tools.base import BaseTool


class PortfolioMetricsTool(BaseTool[dict]):
    """Deterministic portfolio math: allocation, concentration weights, cash buffer,
    and a rough monthly-expense estimate. No LLM, no randomness — same input always
    produces the same numbers."""

    name = "portfolio_metrics_tool"

    def validate(self, **kwargs: Any) -> None:
        if not isinstance(kwargs.get("client"), ClientProfile):
            raise ValueError("client (ClientProfile) is required")

    def _run(self, *, client: ClientProfile, **_: Any) -> dict[str, Any]:
        total_holdings_value = 0.0
        allocation: dict[str, float] = defaultdict(float)
        holding_weights: list[dict[str, Any]] = []
        total_cash = 0.0

        for account in client.accounts:
            if account.account_type in ("checking", "savings"):
                total_cash += account.balance
            for holding in account.holdings:
                total_holdings_value += holding.value
                allocation[holding.asset_class] += holding.value
                if holding.asset_class == "cash":
                    total_cash += holding.value
                holding_weights.append(
                    {
                        "account_id": account.account_id,
                        "symbol": holding.symbol,
                        "value": holding.value,
                    }
                )

        allocation_pct = (
            {
                asset_class: round(value / total_holdings_value, 4)
                for asset_class, value in allocation.items()
            }
            if total_holdings_value > 0
            else {}
        )

        for item in holding_weights:
            item["pct_of_portfolio"] = (
                round(item["value"] / total_holdings_value, 4) if total_holdings_value > 0 else 0.0
            )

        monthly_expenses = _estimate_monthly_expenses(client)
        liquidity_months = round(total_cash / monthly_expenses, 2) if monthly_expenses > 0 else None

        return {
            "total_holdings_value": round(total_holdings_value, 2),
            "total_cash": round(total_cash, 2),
            "allocation_by_asset_class": allocation_pct,
            "holding_weights": holding_weights,
            "monthly_expense_estimate": round(monthly_expenses, 2) if monthly_expenses else None,
            "liquidity_months": liquidity_months,
        }


def _estimate_monthly_expenses(client: ClientProfile) -> float:
    monthly_totals: dict[str, float] = defaultdict(float)
    for txn in client.transactions:
        if txn.type != "debit":
            continue
        month_key = f"{txn.date.year:04d}-{txn.date.month:02d}"
        monthly_totals[month_key] += txn.amount
    if not monthly_totals:
        return 0.0
    return sum(monthly_totals.values()) / len(monthly_totals)
