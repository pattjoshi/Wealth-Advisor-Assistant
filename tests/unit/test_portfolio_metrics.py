from wealth_advisor.schemas.client import Account, ClientProfile, Holding
from wealth_advisor.tools.portfolio_metrics import PortfolioMetricsTool


def _client(accounts: list[Account]) -> ClientProfile:
    return ClientProfile(client_id="c1", full_name="Test", accounts=accounts, transactions=[])


def test_allocation_and_concentration() -> None:
    client = _client(
        [
            Account(
                account_id="A1",
                account_type="brokerage",
                balance=0,
                holdings=[
                    Holding(symbol="AAA", asset_class="equity", quantity=1, value=80),
                    Holding(symbol="BBB", asset_class="bond", quantity=1, value=20),
                ],
            )
        ]
    )
    result = PortfolioMetricsTool().execute(client=client)

    assert result.ok is True
    assert result.data["total_holdings_value"] == 100
    assert result.data["allocation_by_asset_class"]["equity"] == 0.8
    weights = {h["symbol"]: h["pct_of_portfolio"] for h in result.data["holding_weights"]}
    assert weights["AAA"] == 0.8


def test_cash_includes_checking_and_cash_holdings() -> None:
    client = _client(
        [
            Account(account_id="CHK", account_type="checking", balance=1000, holdings=[]),
            Account(
                account_id="BRK",
                account_type="brokerage",
                balance=0,
                holdings=[Holding(symbol="CASH", asset_class="cash", quantity=1, value=500)],
            ),
        ]
    )
    result = PortfolioMetricsTool().execute(client=client)
    assert result.data["total_cash"] == 1500


def test_no_holdings_gives_empty_allocation() -> None:
    client = _client([])
    result = PortfolioMetricsTool().execute(client=client)
    assert result.ok is True
    assert result.data["allocation_by_asset_class"] == {}
    assert result.data["liquidity_months"] is None
