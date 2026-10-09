"""Generate the five mock client files, the mock CRM database, and the anomaly labels
used by Phase 1 onward. Deterministic: same output on every run (fixed random seed)."""

from __future__ import annotations

import json
import random
from datetime import date, timedelta
from pathlib import Path

SEED = 42
REPO_ROOT = Path(__file__).resolve().parent.parent
CLIENTS_DIR = REPO_ROOT / "data" / "clients"
CRM_FILE = REPO_ROOT / "data" / "crm" / "crm_records.json"
LABELS_FILE = REPO_ROOT / "data" / "labels" / "expected_anomalies.json"

BASE_DATE = date(2026, 9, 1)


def _write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=str) + "\n")


def _dates_over_months(rng: random.Random, n: int, months: int = 3) -> list[date]:
    span = months * 30
    offsets = sorted(rng.sample(range(span), n))
    return [BASE_DATE - timedelta(days=span - offset) for offset in offsets]


def build_client_001_clean() -> dict:
    """Clean client, no anomalies — normal recurring transactions, diversified portfolio."""
    rng = random.Random(SEED)
    categories = ["groceries", "utilities", "dining", "transport", "entertainment"]
    txns = []
    for i, d in enumerate(_dates_over_months(rng, 12)):
        category = categories[i % len(categories)]
        txns.append(
            {
                "transaction_id": f"T001-{i:03d}",
                "date": d,
                "amount": round(rng.uniform(20, 180), 2),
                "category": category,
                "payee": f"{category.title()} Co",
                "type": "debit",
            }
        )
    return {
        "client_id": "client_001",
        "full_name": "Alice Morgan",
        "date_of_birth": date(1978, 4, 12),
        "base_currency": "USD",
        "accounts": [
            {
                "account_id": "A001-BRK",
                "account_type": "brokerage",
                "balance": 185_000.0,
                "holdings": [
                    {
                        "symbol": "VTI",
                        "asset_class": "equity",
                        "sector": "broad_market",
                        "quantity": 400,
                        "value": 90_000.0,
                    },
                    {
                        "symbol": "BND",
                        "asset_class": "bond",
                        "sector": "fixed_income",
                        "quantity": 600,
                        "value": 55_000.0,
                    },
                    {
                        "symbol": "VNQ",
                        "asset_class": "real_estate",
                        "sector": "reit",
                        "quantity": 300,
                        "value": 40_000.0,
                    },
                ],
            },
            {
                "account_id": "A001-CHK",
                "account_type": "checking",
                "balance": 22_000.0,
                "holdings": [],
            },
        ],
        "transactions": txns,
    }


def build_client_002_anomalies() -> dict:
    """Seeded anomalies: large transfer, duplicate payment, spending spike, concentration."""
    rng = random.Random(SEED + 1)
    categories = ["groceries", "utilities", "dining"]
    txns = []
    for i, d in enumerate(_dates_over_months(rng, 8, months=2)):
        category = categories[i % len(categories)]
        txns.append(
            {
                "transaction_id": f"T002-{i:03d}",
                "date": d,
                "amount": round(rng.uniform(30, 150), 2),
                "category": category,
                "payee": f"{category.title()} Co",
                "type": "debit",
            }
        )
    # Anomaly 1: unusually large cash withdrawal / transfer out.
    txns.append(
        {
            "transaction_id": "T002-A1",
            "date": BASE_DATE - timedelta(days=10),
            "amount": 45_000.0,
            "category": "transfer",
            "payee": "External Account",
            "type": "transfer_out",
        }
    )
    # Anomaly 2: duplicate payment — same amount and payee within a short window.
    txns.append(
        {
            "transaction_id": "T002-A2a",
            "date": BASE_DATE - timedelta(days=5),
            "amount": 1_200.0,
            "category": "rent",
            "payee": "Skyline Properties",
            "type": "debit",
        }
    )
    txns.append(
        {
            "transaction_id": "T002-A2b",
            "date": BASE_DATE - timedelta(days=4),
            "amount": 1_200.0,
            "category": "rent",
            "payee": "Skyline Properties",
            "type": "debit",
        }
    )
    # Anomaly 3: spending spike — several same-month, same-category transactions.
    for i in range(4):
        txns.append(
            {
                "transaction_id": f"T002-A3-{i}",
                "date": BASE_DATE - timedelta(days=2) - timedelta(days=i),
                "amount": round(rng.uniform(300, 500), 2),
                "category": "shopping",
                "payee": "Luxury Retail",
                "type": "debit",
            }
        )
    return {
        "client_id": "client_002",
        "full_name": "Ben Carter",
        "date_of_birth": date(1985, 11, 2),
        "base_currency": "USD",
        "accounts": [
            {
                "account_id": "A002-BRK",
                "account_type": "brokerage",
                # Anomaly 4: concentration — one holding is most of the portfolio.
                "balance": 120_000.0,
                "holdings": [
                    {
                        "symbol": "TSLA",
                        "asset_class": "equity",
                        "sector": "automotive",
                        "quantity": 500,
                        "value": 95_000.0,
                    },
                    {
                        "symbol": "BND",
                        "asset_class": "bond",
                        "sector": "fixed_income",
                        "quantity": 150,
                        "value": 15_000.0,
                    },
                ],
            },
            {
                "account_id": "A002-CHK",
                "account_type": "checking",
                "balance": 48_000.0,
                "holdings": [],
            },
        ],
        "transactions": txns,
    }


def build_client_003_missing_fields() -> dict:
    """Missing/null optional fields: no date_of_birth, a holding with no sector, an empty
    account, transactions with no payee."""
    rng = random.Random(SEED + 2)
    txns = []
    for i, d in enumerate(_dates_over_months(rng, 6)):
        txns.append(
            {
                "transaction_id": f"T003-{i:03d}",
                "date": d,
                "amount": round(rng.uniform(20, 100), 2),
                "category": "misc",
                "payee": None,
                "type": "debit",
            }
        )
    return {
        "client_id": "client_003",
        "full_name": "Carla Diaz",
        "date_of_birth": None,
        "base_currency": "USD",
        "accounts": [
            {
                "account_id": "A003-BRK",
                "account_type": "brokerage",
                "balance": 60_000.0,
                "holdings": [
                    {
                        "symbol": "VOO",
                        "asset_class": "equity",
                        "sector": None,
                        "quantity": 200,
                        "value": 60_000.0,
                    },
                ],
            },
            {
                "account_id": "A003-SAV",
                "account_type": "savings",
                "balance": 5_000.0,
                "holdings": [],
            },
        ],
        "transactions": txns,
    }


def build_client_004_not_in_crm() -> dict:
    """Valid client file; intentionally absent from crm_records.json."""
    rng = random.Random(SEED + 3)
    txns = []
    for i, d in enumerate(_dates_over_months(rng, 5)):
        txns.append(
            {
                "transaction_id": f"T004-{i:03d}",
                "date": d,
                "amount": round(rng.uniform(25, 120), 2),
                "category": "groceries",
                "payee": "Grocery Co",
                "type": "debit",
            }
        )
    return {
        "client_id": "client_004",
        "full_name": "Derek Nguyen",
        "date_of_birth": date(1990, 6, 20),
        "base_currency": "USD",
        "accounts": [
            {
                "account_id": "A004-CHK",
                "account_type": "checking",
                "balance": 15_000.0,
                "holdings": [],
            },
        ],
        "transactions": txns,
    }


def build_client_005_malformed() -> dict:
    """Malformed transactions: missing required field and wrong type — this file is
    expected to FAIL schema validation with a clear, field-level message."""
    return {
        "client_id": "client_005",
        "full_name": "Elena Petrova",
        "date_of_birth": date(1982, 2, 14),
        "base_currency": "USD",
        "accounts": [
            {
                "account_id": "A005-BRK",
                "account_type": "brokerage",
                "balance": 30_000.0,
                "holdings": [
                    {"symbol": "AAPL", "asset_class": "equity", "quantity": 100, "value": 30_000.0},
                ],
            },
        ],
        "transactions": [
            {
                # missing "transaction_id"
                "date": str(BASE_DATE - timedelta(days=1)),
                "amount": "not-a-number",  # wrong type
                "category": "misc",
                "payee": "Unknown",
                "type": "debit",
            },
        ],
    }


def build_crm_records() -> dict:
    return {
        "client_001": {
            "client_id": "client_001",
            "risk_tolerance": "moderate",
            "goals": ["retirement", "college_fund"],
            "last_contact": date(2026, 7, 15),
            "advisor_notes": "Prefers quarterly check-ins.",
        },
        "client_002": {
            "client_id": "client_002",
            "risk_tolerance": "aggressive",
            "goals": ["wealth_growth"],
            "last_contact": date(2026, 6, 1),
            "advisor_notes": None,
        },
        "client_003": {
            "client_id": "client_003",
            "risk_tolerance": "conservative",
            "goals": ["capital_preservation"],
            "last_contact": None,
            "advisor_notes": None,
        },
        # client_004 intentionally absent — tests the "client not in CRM" path.
        "client_005": {
            "client_id": "client_005",
            "risk_tolerance": "moderate",
            "goals": ["retirement"],
            "last_contact": date(2026, 5, 10),
            "advisor_notes": None,
        },
    }


def build_expected_anomalies() -> dict:
    return {
        "client_002": [
            {"type": "large_transfer", "transaction_id": "T002-A1"},
            {"type": "duplicate_payment", "transaction_ids": ["T002-A2a", "T002-A2b"]},
            {"type": "spending_spike", "category": "shopping"},
            {"type": "concentration", "account_id": "A002-BRK", "symbol": "TSLA"},
        ],
    }


def main() -> None:
    _write(CLIENTS_DIR / "client_001.json", build_client_001_clean())
    _write(CLIENTS_DIR / "client_002.json", build_client_002_anomalies())
    _write(CLIENTS_DIR / "client_003.json", build_client_003_missing_fields())
    _write(CLIENTS_DIR / "client_004.json", build_client_004_not_in_crm())
    _write(CLIENTS_DIR / "client_005.json", build_client_005_malformed())
    _write(CRM_FILE, build_crm_records())
    _write(LABELS_FILE, build_expected_anomalies())
    print(f"Wrote 5 client files to {CLIENTS_DIR}")
    print(f"Wrote CRM records to {CRM_FILE}")
    print(f"Wrote expected anomalies to {LABELS_FILE}")


if __name__ == "__main__":
    main()
