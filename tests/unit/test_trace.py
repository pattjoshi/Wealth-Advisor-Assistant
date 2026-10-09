from wealth_advisor.graph.state import new_state
from wealth_advisor.observability.trace import wrap_node


def test_wrap_node_increments_step_count_and_passes_through_update() -> None:
    state = new_state(run_id="r", client_id="c", thread_id="c")

    def fn(_state: dict) -> dict:
        return {"insights": "done"}

    wrapped = wrap_node("test_node", fn)
    update = wrapped(state)

    assert update["step_count"] == 1
    assert update["insights"] == "done"


def test_wrap_node_catches_unexpected_exception_without_crashing() -> None:
    state = new_state(run_id="r", client_id="c", thread_id="c")

    def fn(_state: dict) -> dict:
        raise RuntimeError("boom")

    wrapped = wrap_node("test_node", fn)
    update = wrapped(state)  # must not raise

    assert update["status"] == "failed"
    assert update["step_count"] == 1
    assert any("boom" in e for e in update["errors"])
    assert any("test_node" in e for e in update["errors"])


def test_wrap_node_preserves_existing_errors_on_exception() -> None:
    state = new_state(run_id="r", client_id="c", thread_id="c")
    state["errors"] = ["earlier problem"]

    def fn(_state: dict) -> dict:
        raise RuntimeError("second problem")

    wrapped = wrap_node("test_node", fn)
    update = wrapped(state)

    assert "earlier problem" in update["errors"]
    assert any("second problem" in e for e in update["errors"])
