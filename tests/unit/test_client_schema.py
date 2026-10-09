from pathlib import Path

import pytest

from wealth_advisor.errors import ClientDataValidationError
from wealth_advisor.schemas.client import ClientProfile
from wealth_advisor.schemas.crm import CrmProfile

CLIENTS_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "clients"
CRM_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "crm" / "crm_records.json"


@pytest.mark.parametrize(
    "filename",
    ["client_001.json", "client_002.json", "client_003.json", "client_004.json"],
)
def test_valid_client_files_load(filename: str) -> None:
    profile = ClientProfile.from_file(CLIENTS_DIR / filename)
    assert profile.client_id == filename.removesuffix(".json")


def test_client_003_has_missing_optional_fields() -> None:
    profile = ClientProfile.from_file(CLIENTS_DIR / "client_003.json")
    assert profile.date_of_birth is None
    assert profile.accounts[0].holdings[0].sector is None


def test_client_005_malformed_transactions_fail_with_clear_message() -> None:
    with pytest.raises(ClientDataValidationError) as exc_info:
        ClientProfile.from_file(CLIENTS_DIR / "client_005.json")

    message = str(exc_info.value)
    assert "transaction_id" in message
    assert "amount" in message


def test_missing_file_raises_clear_error() -> None:
    with pytest.raises(ClientDataValidationError):
        ClientProfile.from_file(CLIENTS_DIR / "does_not_exist.json")


def test_crm_records_load_for_known_clients() -> None:
    import json

    records = json.loads(CRM_FILE.read_text())
    assert "client_004" not in records  # client_004 is intentionally absent from the CRM

    for client_id in ("client_001", "client_002", "client_003", "client_005"):
        profile = CrmProfile.model_validate(records[client_id])
        assert profile.client_id == client_id
