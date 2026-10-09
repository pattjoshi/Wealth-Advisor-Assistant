from wealth_advisor.graph.orchestrator import MAX_STEPS, route
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
