from wealth_advisor.agents.insight import InsightAgent
from wealth_advisor.graph.state import new_state


def test_no_anomalies_gives_reassuring_narrative() -> None:
    state = new_state(run_id="r", client_id="client_001", thread_id="client_001")
    state["anomalies"] = []
    state["risk_score"] = 0.0

    update = InsightAgent().run(state)

    assert "No notable anomalies" in update["insights"]


def test_high_severity_anomaly_triggers_recommendation() -> None:
    state = new_state(run_id="r", client_id="client_002", thread_id="client_002")
    state["anomalies"] = [
        {
            "id": "A1",
            "type": "large_transfer",
            "severity": "high",
            "evidence": {},
            "explanation": "Big transfer out.",
            "is_recurring": False,
        }
    ]
    state["risk_score"] = 0.9

    update = InsightAgent().run(state)

    assert "[HIGH] Big transfer out." in update["insights"]
    assert "Recommended action" in update["insights"]


def test_findings_sorted_highest_severity_first() -> None:
    state = new_state(run_id="r", client_id="c", thread_id="c")
    state["anomalies"] = [
        {
            "id": "A1",
            "type": "t",
            "severity": "low",
            "evidence": {},
            "explanation": "low one",
            "is_recurring": False,
        },
        {
            "id": "A2",
            "type": "t",
            "severity": "high",
            "evidence": {},
            "explanation": "high one",
            "is_recurring": False,
        },
    ]
    state["risk_score"] = 0.5

    update = InsightAgent().run(state)

    lines = update["insights"].splitlines()
    high_idx = next(i for i, line in enumerate(lines) if "high one" in line)
    low_idx = next(i for i, line in enumerate(lines) if "low one" in line)
    assert high_idx < low_idx
