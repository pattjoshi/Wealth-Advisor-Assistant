from wealth_advisor.llm.grounding import extract_numbers, is_grounded, numeric_vocabulary


def _finding(explanation: str, evidence: dict | None = None) -> dict:
    return {
        "id": "A1",
        "type": "t",
        "severity": "high",
        "evidence": evidence or {},
        "explanation": explanation,
        "is_recurring": False,
    }


def test_extract_numbers_ignores_digits_inside_identifiers() -> None:
    numbers = extract_numbers("Client: client_002, transaction T002-A2a, amount $45,000.00")
    assert 45000.0 in numbers
    assert 2.0 not in numbers  # from "client_002" / "T002"


def test_extract_numbers_handles_currency_and_percent() -> None:
    numbers = extract_numbers("$1,200.00 and 86%")
    assert 1200.0 in numbers
    assert 86.0 in numbers


def test_numeric_vocabulary_includes_explanation_numbers() -> None:
    vocab = numeric_vocabulary([_finding("$45,000.00 moved out, 94% of liquid assets.")], 1.0)
    assert 45000.0 in vocab
    assert 94.0 in vocab
    assert 1.0 in vocab  # risk score
    assert 1.0 in vocab  # len(anomalies) == 1


def test_numeric_vocabulary_includes_percent_scaled_evidence() -> None:
    vocab = numeric_vocabulary([_finding("concentration risk", {"pct_of_portfolio": 0.8636})], None)
    assert 86 in vocab or 86.4 in vocab


def test_is_grounded_accepts_text_using_only_known_numbers() -> None:
    vocab = numeric_vocabulary([_finding("$45,000.00 moved out.")], 1.0)
    assert is_grounded("A $45,000.00 transfer was flagged.", vocab) is True


def test_is_grounded_rejects_fabricated_number() -> None:
    vocab = numeric_vocabulary([_finding("$45,000.00 moved out.")], 1.0)
    assert is_grounded("This client owes $999,999 in fees!", vocab) is False


def test_is_grounded_true_for_text_with_no_numbers() -> None:
    vocab = numeric_vocabulary([], 0.0)
    assert is_grounded("No anomalies were detected.", vocab) is True
