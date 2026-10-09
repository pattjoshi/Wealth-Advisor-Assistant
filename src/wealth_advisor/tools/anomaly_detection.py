from __future__ import annotations

import statistics
from collections import defaultdict
from collections.abc import Iterator
from datetime import timedelta
from itertools import count, pairwise
from typing import Any

from wealth_advisor.graph.state import AnomalyFinding
from wealth_advisor.schemas.client import ClientProfile, Transaction
from wealth_advisor.schemas.crm import CrmProfile
from wealth_advisor.tools.base import BaseTool

# Transaction-level thresholds
Z_SCORE_THRESHOLD = 3.5
MIN_TXNS_FOR_Z_SCORE = 4
DUPLICATE_WINDOW_DAYS = 7
LARGE_TRANSFER_PCT_OF_CASH = 0.10
MIN_TXNS_FOR_RARE_CATEGORY = 6
SPIKE_WINDOW_DAYS = 7
SPIKE_MIN_COUNT = 3

# Risk-level thresholds
CONCENTRATION_THRESHOLD = 0.60
LOW_LIQUIDITY_MONTHS = 2.0

SEVERITY_WEIGHT = {"low": 1, "medium": 2, "high": 3}


class AnomalyDetectionTool(BaseTool[dict]):
    """All ten deterministic anomaly/risk checks from planning.md Sec 4.5. Every
    finding is a plain statistical or threshold rule — no LLM — so results are
    reproducible and each one comes with the evidence that triggered it."""

    name = "anomaly_detection_tool"

    def validate(self, **kwargs: Any) -> None:
        if not isinstance(kwargs.get("client"), ClientProfile):
            raise ValueError("client (ClientProfile) is required")
        if "metrics" not in kwargs:
            raise ValueError("metrics is required")

    def _run(
        self,
        *,
        client: ClientProfile,
        metrics: dict[str, Any],
        crm_profile: CrmProfile | None = None,
        **_: Any,
    ) -> dict[str, Any]:
        counter = count(1)
        assumptions: list[str] = []
        findings: list[AnomalyFinding] = []

        findings += _check_unusual_amount(client, counter)
        findings += _check_duplicate_payment(client, counter)
        findings += _check_large_transfer(client, metrics, counter)
        findings += _check_unusual_category(client, counter)
        findings += _check_spending_spike(client, counter)
        findings += _check_income_drop(client, counter, assumptions)
        findings += _check_portfolio_drawdown(assumptions)
        findings += _check_concentration(metrics, counter)
        findings += _check_risk_profile_mismatch(metrics, crm_profile, counter, assumptions)
        findings += _check_low_liquidity(metrics, counter)

        return {
            "findings": findings,
            "risk_score": _compute_risk_score(findings),
            "assumptions": assumptions,
        }


def _compute_risk_score(findings: list[AnomalyFinding]) -> float:
    if not findings:
        return 0.0
    total = sum(SEVERITY_WEIGHT[f["severity"]] for f in findings)
    return round(min(1.0, total / 10), 2)


def _next_id(counter: Iterator[int]) -> str:
    return f"ANOM-{next(counter):03d}"


def _check_unusual_amount(client: ClientProfile, counter: Iterator[int]) -> list[AnomalyFinding]:
    """Transaction check: robust (median/MAD) z-score per category — flags an amount
    far outside this client's own normal range for that category."""
    by_category: dict[str, list[Transaction]] = defaultdict(list)
    for txn in client.transactions:
        if txn.type == "debit":
            by_category[txn.category].append(txn)

    findings: list[AnomalyFinding] = []
    for category, txns in by_category.items():
        if len(txns) < MIN_TXNS_FOR_Z_SCORE:
            continue
        amounts = [t.amount for t in txns]
        median = statistics.median(amounts)
        mad = statistics.median([abs(a - median) for a in amounts])
        if mad == 0:
            continue
        for txn, amount in zip(txns, amounts, strict=True):
            z = 0.6745 * (amount - median) / mad
            if abs(z) > Z_SCORE_THRESHOLD:
                findings.append(
                    AnomalyFinding(
                        id=_next_id(counter),
                        type="unusual_amount",
                        severity="high" if abs(z) > 5 else "medium",
                        evidence={
                            "transaction_id": txn.transaction_id,
                            "category": category,
                            "amount": amount,
                            "category_median": median,
                            "z_score": round(z, 2),
                        },
                        explanation=(
                            f"${amount:,.2f} in '{category}' is far outside this client's "
                            f"usual range for that category (median ${median:,.2f})."
                        ),
                        is_recurring=False,
                    )
                )
    return findings


def _check_duplicate_payment(client: ClientProfile, counter: Iterator[int]) -> list[AnomalyFinding]:
    """Transaction check: same amount + payee within a short window looks like one
    payment charged twice, not two separate purchases."""
    by_key: dict[tuple[float, str], list[Transaction]] = defaultdict(list)
    for txn in client.transactions:
        if txn.type == "debit" and txn.payee:
            by_key[(txn.amount, txn.payee)].append(txn)

    findings: list[AnomalyFinding] = []
    for (amount, payee), txns in by_key.items():
        if len(txns) < 2:
            continue
        txns_sorted = sorted(txns, key=lambda t: t.date)
        for earlier, later in pairwise(txns_sorted):
            gap_days = (later.date - earlier.date).days
            if timedelta(days=gap_days) <= timedelta(days=DUPLICATE_WINDOW_DAYS):
                findings.append(
                    AnomalyFinding(
                        id=_next_id(counter),
                        type="duplicate_payment",
                        severity="medium",
                        evidence={
                            "transaction_ids": [earlier.transaction_id, later.transaction_id],
                            "amount": amount,
                            "payee": payee,
                            "days_apart": gap_days,
                        },
                        explanation=(
                            f"Two ${amount:,.2f} payments to '{payee}' {gap_days} day(s) "
                            "apart look like a duplicate, not two separate charges."
                        ),
                        is_recurring=False,
                    )
                )
    return findings


def _check_large_transfer(
    client: ClientProfile, metrics: dict[str, Any], counter: Iterator[int]
) -> list[AnomalyFinding]:
    """Transaction check: a withdrawal or transfer-out that's a large share of liquid
    assets in one shot."""
    liquid = float(metrics.get("total_cash") or 0.0)
    if liquid <= 0:
        return []
    threshold = liquid * LARGE_TRANSFER_PCT_OF_CASH

    findings: list[AnomalyFinding] = []
    for txn in client.transactions:
        if txn.type in ("withdrawal", "transfer_out") and txn.amount > threshold:
            findings.append(
                AnomalyFinding(
                    id=_next_id(counter),
                    type="large_transfer",
                    severity="high" if txn.amount > liquid * 0.5 else "medium",
                    evidence={
                        "transaction_id": txn.transaction_id,
                        "amount": txn.amount,
                        "pct_of_liquid_assets": round(txn.amount / liquid, 2),
                    },
                    explanation=(
                        f"${txn.amount:,.2f} moved out in one transaction is "
                        f"{round(txn.amount / liquid * 100)}% of this client's liquid assets."
                    ),
                    is_recurring=False,
                )
            )
    return findings


def _check_unusual_category(client: ClientProfile, counter: Iterator[int]) -> list[AnomalyFinding]:
    """Transaction check: a category/payee never seen elsewhere in this client's
    history. Only runs once there's enough history to judge rarity."""
    debits = [t for t in client.transactions if t.type == "debit"]
    if len(debits) < MIN_TXNS_FOR_RARE_CATEGORY:
        return []

    counts: dict[str, int] = defaultdict(int)
    first_seen: dict[str, Transaction] = {}
    for txn in debits:
        counts[txn.category] += 1
        first_seen.setdefault(txn.category, txn)

    findings: list[AnomalyFinding] = []
    for category, txn_count in counts.items():
        if txn_count == 1:
            txn = first_seen[category]
            findings.append(
                AnomalyFinding(
                    id=_next_id(counter),
                    type="unusual_category",
                    severity="low",
                    evidence={"transaction_id": txn.transaction_id, "category": category},
                    explanation=f"'{category}' has never appeared in this client's history before.",
                    is_recurring=False,
                )
            )
    return findings


def _check_spending_spike(client: ClientProfile, counter: Iterator[int]) -> list[AnomalyFinding]:
    """Trend check: a burst of same-category transactions clustered in a short window —
    more robust than month-boundary comparisons when the mock data only spans a few
    months."""
    by_category: dict[str, list[Transaction]] = defaultdict(list)
    for txn in client.transactions:
        if txn.type == "debit":
            by_category[txn.category].append(txn)

    findings: list[AnomalyFinding] = []
    for category, txns in by_category.items():
        txns_sorted = sorted(txns, key=lambda t: t.date)
        for i, start in enumerate(txns_sorted):
            window = [
                t
                for t in txns_sorted[i:]
                if (t.date - start.date) <= timedelta(days=SPIKE_WINDOW_DAYS)
            ]
            if len(window) >= SPIKE_MIN_COUNT:
                window_total = sum(t.amount for t in window)
                findings.append(
                    AnomalyFinding(
                        id=_next_id(counter),
                        type="spending_spike",
                        severity="medium",
                        evidence={
                            "category": category,
                            "transaction_ids": [t.transaction_id for t in window],
                            "window_days": SPIKE_WINDOW_DAYS,
                            "window_total": round(window_total, 2),
                        },
                        explanation=(
                            f"{len(window)} '{category}' charges totalling "
                            f"${window_total:,.2f} within {SPIKE_WINDOW_DAYS} days looks like "
                            "a spending burst, not normal recurring spend."
                        ),
                        is_recurring=False,
                    )
                )
                break  # one finding per category is enough
    return findings


def _check_income_drop(
    client: ClientProfile, counter: Iterator[int], assumptions: list[str]
) -> list[AnomalyFinding]:
    """Trend check: this month's income well below the recent average. Skipped (with
    an assumption noted) when there isn't enough income history to set a baseline."""
    income_types = {"credit", "deposit", "transfer_in"}
    by_month: dict[str, float] = defaultdict(float)
    for txn in client.transactions:
        if txn.type in income_types:
            month_key = f"{txn.date.year:04d}-{txn.date.month:02d}"
            by_month[month_key] += txn.amount

    if len(by_month) < 2:
        assumptions.append(
            "income_drop check skipped: not enough income transactions on file to "
            "establish a baseline"
        )
        return []

    months_sorted = sorted(by_month)
    latest_month = months_sorted[-1]
    latest_total = by_month[latest_month]
    baseline = statistics.mean(by_month[m] for m in months_sorted[:-1])

    if baseline > 0 and latest_total <= baseline * 0.6:
        return [
            AnomalyFinding(
                id=_next_id(counter),
                type="income_drop",
                severity="medium",
                evidence={
                    "month": latest_month,
                    "month_total": round(latest_total, 2),
                    "prior_average": round(baseline, 2),
                },
                explanation=(
                    f"Income this month (${latest_total:,.2f}) is well below this "
                    f"client's recent average (${baseline:,.2f})."
                ),
                is_recurring=False,
            )
        ]
    return []


def _check_portfolio_drawdown(assumptions: list[str]) -> list[AnomalyFinding]:
    """Trend check: % fall from the portfolio's peak value. Always skipped here — the
    mock data only has a current snapshot, not a value history, which this check
    needs. Documented honestly rather than faked."""
    assumptions.append(
        "portfolio_drawdown check skipped: no historical portfolio value snapshots are "
        "available in this mock dataset (only a current snapshot); production would "
        "need a time-series of account values"
    )
    return []


def _check_concentration(metrics: dict[str, Any], counter: Iterator[int]) -> list[AnomalyFinding]:
    """Risk check: a single holding dominating the portfolio."""
    findings: list[AnomalyFinding] = []
    for holding in metrics.get("holding_weights", []):
        pct = holding.get("pct_of_portfolio", 0.0)
        if pct >= CONCENTRATION_THRESHOLD:
            findings.append(
                AnomalyFinding(
                    id=_next_id(counter),
                    type="concentration",
                    severity="high",
                    evidence={
                        "account_id": holding["account_id"],
                        "symbol": holding["symbol"],
                        "pct_of_portfolio": pct,
                    },
                    explanation=(
                        f"{holding['symbol']} alone makes up {round(pct * 100)}% of this "
                        "client's holdings — a single-position concentration risk."
                    ),
                    is_recurring=False,
                )
            )
    return findings


def _check_risk_profile_mismatch(
    metrics: dict[str, Any],
    crm_profile: CrmProfile | None,
    counter: Iterator[int],
    assumptions: list[str],
) -> list[AnomalyFinding]:
    """Risk check: portfolio allocation vs. the CRM's stated risk tolerance. Skipped
    (with an assumption noted) when the CRM profile is missing or degraded."""
    if crm_profile is None or crm_profile.status == "degraded":
        assumptions.append(
            "risk_profile_mismatch check skipped: CRM risk tolerance unavailable or degraded"
        )
        return []

    equity_ratio = float(metrics.get("allocation_by_asset_class", {}).get("equity", 0.0))

    mismatch: str | None = None
    if crm_profile.risk_tolerance == "conservative" and equity_ratio > 0.6:
        mismatch = f"conservative client holds {round(equity_ratio * 100)}% equity"
    elif crm_profile.risk_tolerance == "aggressive" and equity_ratio < 0.2:
        mismatch = f"aggressive client holds only {round(equity_ratio * 100)}% equity"

    if mismatch is None:
        return []

    return [
        AnomalyFinding(
            id=_next_id(counter),
            type="risk_profile_mismatch",
            severity="medium",
            evidence={"risk_tolerance": crm_profile.risk_tolerance, "equity_ratio": equity_ratio},
            explanation=f"Portfolio allocation doesn't match the CRM risk profile: {mismatch}.",
            is_recurring=False,
        )
    ]


def _check_low_liquidity(metrics: dict[str, Any], counter: Iterator[int]) -> list[AnomalyFinding]:
    """Risk check: cash on hand below a healthy number of months of expenses."""
    months = metrics.get("liquidity_months")
    if months is None or months >= LOW_LIQUIDITY_MONTHS:
        return []
    return [
        AnomalyFinding(
            id=_next_id(counter),
            type="low_liquidity",
            severity="high" if months < 1 else "medium",
            evidence={"liquidity_months": months},
            explanation=(
                f"This client has about {months} month(s) of expenses in cash — "
                "below a healthy buffer."
            ),
            is_recurring=False,
        )
    ]
