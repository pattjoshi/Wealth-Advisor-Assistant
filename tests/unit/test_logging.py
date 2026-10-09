import json

from wealth_advisor.observability.logging import configure_logging, get_logger, mask_pii


def test_mask_pii_redacts_known_top_level_keys() -> None:
    event = {"full_name": "Jane Doe", "date_of_birth": "1990-01-01", "amount": 50}
    masked = mask_pii(None, "info", event)

    assert masked["full_name"] == "***"
    assert masked["date_of_birth"] == "***"
    assert masked["amount"] == 50


def test_mask_pii_recurses_into_nested_dicts_and_lists() -> None:
    event = {
        "client": {"full_name": "Jane Doe", "payee": "ACME"},
        "items": [{"payee": "X"}, {"payee": "Y"}],
    }
    masked = mask_pii(None, "info", event)

    assert masked["client"]["full_name"] == "***"
    assert masked["client"]["payee"] == "***"
    assert masked["items"][0]["payee"] == "***"
    assert masked["items"][1]["payee"] == "***"


def test_mask_pii_leaves_none_values_and_non_pii_keys_alone() -> None:
    event = {"full_name": None, "client_id": "client_001", "amount": 10}
    masked = mask_pii(None, "info", event)

    assert masked["full_name"] is None
    assert masked["client_id"] == "client_001"
    assert masked["amount"] == 10


def test_configure_logging_writes_json_lines_with_run_id(tmp_path) -> None:
    log_file = tmp_path / "run.jsonl"
    configure_logging(log_level="INFO", log_file=log_file)
    logger = get_logger()
    logger.bind(run_id="r1").info("test_event", foo="bar")

    lines = log_file.read_text().strip().splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["run_id"] == "r1"
    assert entry["event"] == "test_event"
    assert entry["foo"] == "bar"


def test_configure_logging_masks_pii_end_to_end(tmp_path) -> None:
    log_file = tmp_path / "run.jsonl"
    configure_logging(log_level="INFO", log_file=log_file)
    logger = get_logger()
    logger.info("client_loaded", full_name="Jane Doe", client_id="client_001")

    entry = json.loads(log_file.read_text().strip().splitlines()[0])
    assert entry["full_name"] == "***"
    assert entry["client_id"] == "client_001"
