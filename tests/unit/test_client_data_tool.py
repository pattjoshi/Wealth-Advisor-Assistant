from pathlib import Path

from wealth_advisor.tools.client_data import ClientDataTool

CLIENTS_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "clients"


def test_valid_client_returns_ok_result() -> None:
    tool = ClientDataTool(CLIENTS_DIR)
    result = tool.execute(client_id="client_001")

    assert result.ok is True
    assert result.data.client_id == "client_001"
    assert result.source == "client_data_tool"


def test_malformed_client_returns_failed_result_not_an_exception() -> None:
    tool = ClientDataTool(CLIENTS_DIR)
    result = tool.execute(client_id="client_005")

    assert result.ok is False
    assert result.data is None
    assert "transaction_id" in result.error


def test_missing_client_id_fails_validation() -> None:
    tool = ClientDataTool(CLIENTS_DIR)
    result = tool.execute()

    assert result.ok is False
    assert "client_id is required" in result.error
