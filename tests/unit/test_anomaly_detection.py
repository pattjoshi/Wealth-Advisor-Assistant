import json
from datetime import date, timedelta
from pathlib import Path

from wealth_advisor.schemas.client import Account, ClientProfile, Holding, Transaction
from wealth_advisor.schemas.crm import CrmProfile
from wealth_advisor.tools.anomaly_detection import AnomalyDetectionTool
from wealth_advisor.tools.portfolio_metrics import PortfolioMetricsTool

CLIENTS_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "clients"
LABELS_FILE = (
    Path(__file__).resolve().parent.parent.parent / "data" / "labels" / "expected_anomalies.json"
)

BASE = date(2026, 9, 1)


def _txn(**kwargs) -> Transaction:
    defaults = {
        "transaction_id": "T1",
        "date": BASE,
        "amount": 50.0,
        "category": "groceries",
        "payee": "Store",
        "type": "debit",
    }
    defaults.update(kwargs)
    return Transaction(**defaults)


def _client(
    transactions: list[Transaction], accounts: list[Account] | None = None
) -> ClientProfile:
    return ClientProfile(
        client_id="c1", full_name="Test", accounts=accounts or [], transactions=transactions
    )


def _run(client: ClientProfile, crm_profile: CrmProfile | None = None) -> dict:
    metrics = PortfolioMetricsTool().execute(client=client).data
    result = AnomalyDetectionTool().execute(client=client, metrics=metrics, crm_profile=crm_profile)
    assert result.ok is True
    return result.data


def test_duplicate_payment_detected() -> None:
    client = _client(
        [
            _txn(transaction_id="T1", amount=1200, payee="Landlord", date=BASE),
            _txn(transaction_id="T2", amount=1200, payee="Landlord", date=BASE + timedelta(days=1)),
        ]
    )
    data = _run(client)
    types = [f["type"] for f in data["findings"]]
    assert "duplicate_payment" in types


def test_duplicate_payment_not_flagged_outside_window() -> None:
    client = _client(
        [
            _txn(transaction_id="T1", amount=1200, payee="Landlord", date=BASE),
            _txn(
                transaction_id="T2", amount=1200, payee="Landlord", date=BASE + timedelta(days=30)
            ),
        ]
    )
    data = _run(client)
    assert "duplicate_payment" not in [f["type"] for f in data["findings"]]


def test_large_transfer_detected() -> None:
    client = _client(
        [_txn(transaction_id="T1", amount=9000, type="transfer_out", category="transfer")],
        accounts=[Account(account_id="CHK", account_type="checking", balance=10000, holdings=[])],
    )
    data = _run(client)
    findings = [f for f in data["findings"] if f["type"] == "large_transfer"]
    assert len(findings) == 1
    assert findings[0]["severity"] == "high"


def test_large_transfer_not_flagged_when_small() -> None:
    client = _client(
        [_txn(transaction_id="T1", amount=100, type="transfer_out", category="transfer")],
        accounts=[Account(account_id="CHK", account_type="checking", balance=10000, holdings=[])],
    )
    data = _run(client)
    assert "large_transfer" not in [f["type"] for f in data["findings"]]


def test_spending_spike_detected_for_burst() -> None:
    txns = [
        _txn(transaction_id=f"T{i}", amount=300, category="shopping", date=BASE + timedelta(days=i))
        for i in range(3)
    ]
    data = _run(_client(txns))
    assert "spending_spike" in [f["type"] for f in data["findings"]]


def test_spending_spike_not_flagged_when_spread_out() -> None:
    txns = [
        _txn(
            transaction_id=f"T{i}",
            amount=300,
            category="shopping",
            date=BASE + timedelta(days=i * 30),
        )
        for i in range(3)
    ]
    data = _run(_client(txns))
    assert "spending_spike" not in [f["type"] for f in data["findings"]]


def test_concentration_detected() -> None:
    client = _client(
        [],
        accounts=[
            Account(
                account_id="BRK",
                account_type="brokerage",
                balance=0,
                holdings=[
                    Holding(symbol="BIG", asset_class="equity", quantity=1, value=90),
                    Holding(symbol="SMALL", asset_class="bond", quantity=1, value=10),
                ],
            )
        ],
    )
    data = _run(client)
    findings = [f for f in data["findings"] if f["type"] == "concentration"]
    assert len(findings) == 1
    assert findings[0]["evidence"]["symbol"] == "BIG"


def test_concentration_not_flagged_when_diversified() -> None:
    client = _client(
        [],
        accounts=[
            Account(
                account_id="BRK",
                account_type="brokerage",
                balance=0,
                holdings=[
                    Holding(symbol="A", asset_class="equity", quantity=1, value=40),
                    Holding(symbol="B", asset_class="bond", quantity=1, value=35),
                    Holding(symbol="C", asset_class="real_estate", quantity=1, value=25),
                ],
            )
        ],
    )
    data = _run(client)
    assert "concentration" not in [f["type"] for f in data["findings"]]


def test_low_liquidity_detected() -> None:
    txns = [
        _txn(transaction_id=f"T{i}", amount=1000, date=BASE - timedelta(days=30 * i))
        for i in range(3)
    ]
    client = _client(
        txns,
        accounts=[Account(account_id="CHK", account_type="checking", balance=100, holdings=[])],
    )
    data = _run(client)
    assert "low_liquidity" in [f["type"] for f in data["findings"]]


def test_risk_profile_mismatch_detected_for_conservative_client_with_high_equity() -> None:
    client = _client(
        [],
        accounts=[
            Account(
                account_id="BRK",
                account_type="brokerage",
                balance=0,
                holdings=[Holding(symbol="X", asset_class="equity", quantity=1, value=100)],
            )
        ],
    )
    crm = CrmProfile(client_id="c1", risk_tolerance="conservative")
    data = _run(client, crm_profile=crm)
    assert "risk_profile_mismatch" in [f["type"] for f in data["findings"]]


def test_risk_profile_mismatch_skipped_when_crm_degraded() -> None:
    client = _client(
        [],
        accounts=[
            Account(
                account_id="BRK",
                account_type="brokerage",
                balance=0,
                holdings=[Holding(symbol="X", asset_class="equity", quantity=1, value=100)],
            )
        ],
    )
    crm = CrmProfile(client_id="c1", risk_tolerance="conservative", status="degraded")
    data = _run(client, crm_profile=crm)
    assert "risk_profile_mismatch" not in [f["type"] for f in data["findings"]]
    assert any("risk_profile_mismatch check skipped" in a for a in data["assumptions"])


def test_portfolio_drawdown_always_skipped_with_assumption() -> None:
    data = _run(_client([]))
    assert any("portfolio_drawdown check skipped" in a for a in data["assumptions"])


def test_risk_score_zero_with_no_findings() -> None:
    data = _run(_client([]))
    assert data["risk_score"] == 0.0


def test_client_001_clean_has_no_findings() -> None:
    client = ClientProfile.from_file(CLIENTS_DIR / "client_001.json")
    data = _run(client)
    assert data["findings"] == []


def test_client_002_matches_expected_anomaly_types() -> None:
    client = ClientProfile.from_file(CLIENTS_DIR / "client_002.json")
    data = _run(client)

    expected = json.loads(LABELS_FILE.read_text())["client_002"]
    expected_types = {item["type"] for item in expected}
    found_types = {f["type"] for f in data["findings"]}

    assert found_types == expected_types
