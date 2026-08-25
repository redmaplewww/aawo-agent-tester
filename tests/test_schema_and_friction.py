from __future__ import annotations

from codex_agent_tester.friction import find_friction
from codex_agent_tester.models import FindingKind, JourneyStep, RawObservation
from codex_agent_tester.schema import infer_schema, validate


def test_schema_validator_is_fail_closed_for_required_and_type():
    schema = {"type": "object", "required": ["answer"], "properties": {"answer": {"type": "string"}}}
    assert validate({"answer": "ok"}, schema) == ()
    assert validate({}, schema) == ("$.answer: required field is missing",)
    assert validate({"answer": 3}, schema) == ("$.answer: expected string, got int",)


def test_infer_schema_is_deterministic():
    assert infer_schema({"a": 1}) == {
        "type": "object",
        "properties": {"a": {"type": "integer"}},
        "required": ["a"],
        "additionalProperties": True,
    }


def test_friction_finding_is_bound_to_customer_steps():
    findings = find_friction(
        "run-1",
        (
            JourneyStep("one", "user_input", {"question": "same"}),
            JourneyStep("two", "user_input", {"question": "same"}),
        ),
        (("one", RawObservation(status="failed", error="internal failure")),),
    )
    assert {item.kind for item in findings} == {FindingKind.HUMAN_FRICTION}
    assert all(item.run_id == "run-1" for item in findings)
