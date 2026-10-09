from wealth_advisor.graph.orchestrator import MAX_STEPS, decide, route
from wealth_advisor.graph.state import new_state


def test_routes_to_data_fetcher_first() -> None:
    state = new_state(run_id="r", client_id="c", thread_id="c")
    assert route(state) == "data_fetcher"


def test_routes_to_analyzer_after_data_fetcher() -> None:
    state = new_state(run_id="r", client_id="c", thread_id="c")
    state["trace"] = [{"agent": "data_fetcher"}]
    assert route(state) == "analyzer"


def test_routes_to_insight_after_analyzer() -> None:
    state = new_state(run_id="r", client_id="c", thread_id="c")
    state["trace"] = [{"agent": "data_fetcher"}, {"agent": "analyzer"}]
    assert route(state) == "insight"


def test_routes_to_finalize_after_all_stages() -> None:
    state = new_state(run_id="r", client_id="c", thread_id="c")
    state["trace"] = [{"agent": "data_fetcher"}, {"agent": "analyzer"}, {"agent": "insight"}]
    assert route(state) == "finalize"


def test_routes_to_finalize_immediately_on_failed_status() -> None:
    state = new_state(run_id="r", client_id="c", thread_id="c")
    state["status"] = "failed"
    assert route(state) == "finalize"


def test_max_step_guard_forces_finalize() -> None:
    state = new_state(run_id="r", client_id="c", thread_id="c")
    state["step_count"] = MAX_STEPS
    assert route(state) == "finalize"


def test_decide_gives_a_reason_alongside_the_next_node() -> None:
    state = new_state(run_id="r", client_id="c", thread_id="c")

    next_node, reason = decide(state)

    assert next_node == "data_fetcher"
    assert "has not run yet" in reason


def test_decide_reason_explains_failed_short_circuit() -> None:
    state = new_state(run_id="r", client_id="c", thread_id="c")
    state["status"] = "failed"

    next_node, reason = decide(state)

    assert next_node == "finalize"
    assert "fail-safe" in reason


def test_decide_reason_explains_max_step_guard() -> None:
    state = new_state(run_id="r", client_id="c", thread_id="c")
    state["step_count"] = MAX_STEPS

    next_node, reason = decide(state)

    assert next_node == "finalize"
    assert "max step limit" in reason


def test_decide_reason_when_all_stages_done() -> None:
    state = new_state(run_id="r", client_id="c", thread_id="c")
    state["trace"] = [{"agent": "data_fetcher"}, {"agent": "analyzer"}, {"agent": "insight"}]

    next_node, reason = decide(state)

    assert next_node == "finalize"
    assert "all stages completed" in reason
