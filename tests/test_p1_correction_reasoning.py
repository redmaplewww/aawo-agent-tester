from __future__ import annotations

import asyncio
import json
import time
from types import SimpleNamespace

import pytest

from codex_agent_tester import (
    AgentContractProfile,
    AsyncJobAdapter,
    CallableAdapter,
    CodexCustomerTester,
    CodexReasoner,
    MINIMUM_COVERAGE,
    Correction,
    CorrectionImpactAnalyzer,
    CustomerJourney,
    CustomerSimulationRunner,
    EvidenceLedger,
    EvolutionGovernor,
    FixtureEnvironment,
    JourneyStep,
    RawObservation,
    ReasoningProviderError,
    ReasoningResponse,
    RunStatus,
    UnderstandingEngine,
    proposal_from_response,
)


def run(coro):
    return asyncio.run(coro)


def test_profile_can_be_reloaded_after_user_correction():
    ledger = EvidenceLedger()
    engine = UnderstandingEngine(ledger)
    profile = engine.create_profile("agent-1", "callable-1", output_schema={"type": "string"})
    corrected = engine.apply_correction(
        profile,
        Correction("corr-profile", "output_schema", {"type": "string"}, {"type": "object"}, "客户确认返回结构化对象", ("customer-1",)),
    )
    reloaded = engine.load_profile("agent-1")
    assert reloaded.revision == corrected.revision
    assert reloaded.output_schema == {"type": "object"}
    assert any(item.status.value == "confirmed" for item in reloaded.hypotheses)


def test_correction_impact_selects_minimum_explicit_journey():
    ledger = EvidenceLedger()
    analyzer = CorrectionImpactAnalyzer(ledger)
    journeys = (
        CustomerJourney("journey-a", "query", (JourneyStep("ask", "user_input", {"question": "a"}),)),
        CustomerJourney("journey-b", "query", (JourneyStep("ask", "user_input", {"question": "b"}),)),
    )
    plan = analyzer.plan(Correction("corr-output", "output_schema", None, {"type": "object"}, "output changed", (), ("journey-b",)), journeys)
    assert plan.selected_scenario_ids == ("journey-b",)
    assert ledger.get(plan.plan_id)["record_type"] == "regression.plan"


def test_regression_plan_executes_only_selected_scenario():
    ledger = EvidenceLedger()
    analyzer = CorrectionImpactAnalyzer(ledger)
    runner = CustomerSimulationRunner(ledger)
    profile = AgentContractProfile("agent-1", "callable-1", output_schema={"type": "object", "required": ["answer"]})
    journeys = (
        CustomerJourney("a", "a", (JourneyStep("ask", "user_input", {"q": "a"}),)),
        CustomerJourney("b", "b", (JourneyStep("ask", "user_input", {"q": "b"}),)),
    )
    plan = analyzer.plan(Correction("corr-run", "output_schema", None, None, "changed", (), ("b",)), journeys)
    runs = run(analyzer.execute(plan, profile, journeys, CallableAdapter("callable-1", lambda payload: {"answer": payload["q"]}), runner))
    assert [item.scenario_id for item in runs] == ["b"]
    assert ledger.get(f"{plan.plan_id}_completed")["payload"]["run_statuses"] == ["pass"]


def test_codex_proposal_parser_and_governor_are_fail_closed():
    response = ReasoningResponse("resp-1", "codex", '{"kind":"contract","base_revision":2,"proposed_change":{"path":"output_schema"},"evidence_ids":["ev-1"],"risk":"high"}', {})
    proposal = proposal_from_response(response)
    ledger = EvidenceLedger()
    governor = EvolutionGovernor(ledger)
    governor.submit(proposal)
    with pytest.raises(PermissionError):
        governor.decide(proposal, decision="approved", decided_by="model", reason="model suggested it")
    assert governor.decide(proposal, decision="shadow", decided_by="operator", reason="observe first", human_approved=True).decision == "shadow"


def test_codex_reasoner_uses_official_sdk_boundary_without_http_provider():
    class FakeThread:
        def run(self, prompt, *, output_schema=None):
            assert "[SYSTEM]" in prompt
            assert output_schema is not None
            return SimpleNamespace(id="turn-1", status="completed", final_response='{"ok":true}', usage=None)

    class FakeCodex:
        def thread_start(self, **kwargs):
            assert kwargs["ephemeral"] is True
            return FakeThread()

        def close(self):
            return None

    reasoner = CodexReasoner(client_factory=FakeCodex)
    response = run(reasoner.complete(({"role": "system", "content": "read-only"}, {"role": "user", "content": "inspect"}), response_schema={"type": "object"}))
    assert response.response_id == "turn-1"
    assert response.json_object() == {"ok": True}
    reasoner.close()


def test_codex_reasoner_turn_timeout_is_fail_closed():
    class SlowThread:
        def run(self, prompt, *, output_schema=None):
            time.sleep(0.05)

    class SlowCodex:
        def thread_start(self, **kwargs):
            return SlowThread()

        def close(self):
            return None

    reasoner = CodexReasoner(client_factory=SlowCodex, turn_timeout=0.001)
    with pytest.raises(ReasoningProviderError, match="timed out"):
        run(reasoner.complete(({"role": "user", "content": "wait"},), response_schema={"type": "object"}))
    reasoner.close()


class FakeReasoner:
    model = "codex-test"

    def __init__(self, plan, review):
        self.responses = [plan, review]
        self.calls = 0

    async def complete(self, messages, *, response_schema=None):
        assert response_schema is not None
        value = self.responses[self.calls]
        self.calls += 1
        return ReasoningResponse(f"response-{self.calls}", self.model, value, {})


class DimensionReasoner(FakeReasoner):
    supports_dimension_planning = True


def _complete_plan(*, missing: tuple[str, ...] = ()) -> str:
    dimensions = ["normal_success", "invalid_or_incomplete_input", "output_contract", "failure_recovery", "repeated_input_or_correction"]
    journeys = []
    checks = []
    for index, dimension in enumerate(dimensions):
        if dimension in missing:
            continue
        scenario = f"scenario-{dimension}"
        journeys.append({
            "scenario_id": scenario,
            "goal": dimension,
            "coverage_dimensions": [dimension],
            "steps": [
                {"step_id": "send", "kind": "user_input", "payload": {"question": dimension}},
                {"step_id": "check", "kind": "expect", "assertions": [{"kind": "contains_keys", "keys": ["answer"]}]},
            ],
        })
        checks.append({"check_id": f"check-{index}", "dimension": dimension, "scenario_ids": [scenario]})
    return __import__("json").dumps({
        "profile": {"agent_id": "codex-discovered", "purpose": "answer customers", "output_schema": {"type": "object", "required": ["answer"]}},
        "journeys": journeys,
        "completeness_checks": checks,
        "limitations": [],
    })


def test_codex_customer_tester_runs_realistic_journeys_and_completeness_review():
    reasoner = FakeReasoner(_complete_plan(), '{"summary":"all evidence reviewed","findings":[],"missing_coverage":[]}')
    ledger = EvidenceLedger()
    tester = CodexCustomerTester(ledger, reasoner)
    report = run(tester.test(
        CallableAdapter("customer-agent", lambda payload: {"answer": payload["question"]}),
        target={"channel": "callable", "name": "fixture-agent"},
        customer_goal="客户要得到可用回答",
    ))
    assert report.status == "pass"
    assert len(report.runs) == 5
    assert {item.status for item in report.coverage} == {"covered"}
    assert report.review.status == "pass"
    assert any(item["record_type"] == "codex.plan.created" for item in ledger.records())


def test_codex_customer_tester_merges_bounded_dimension_turns():
    complete = json.loads(_complete_plan())
    parts = []
    for index, dimension in enumerate(MINIMUM_COVERAGE):
        parts.append(json.dumps({
            "profile": complete["profile"],
            "journeys": [complete["journeys"][index]],
            "completeness_checks": [complete["completeness_checks"][index]],
            "limitations": [],
        }))
    reasoner = DimensionReasoner(parts[0], parts[1])
    reasoner.responses = parts + ['{"summary":"all evidence reviewed","findings":[],"missing_coverage":[]}']
    report = run(CodexCustomerTester(EvidenceLedger(), reasoner).test(
        CallableAdapter("customer-agent", lambda payload: {"answer": payload["question"]}),
        target={"channel": "callable"},
        customer_goal="客户要得到可用回答",
    ))
    assert report.status == "pass"
    assert len(report.runs) == len(MINIMUM_COVERAGE)
    assert report.plan is not None and report.plan.response_id.startswith("dimensionwise:")


def test_codex_customer_tester_reports_missing_implementation_coverage():
    reasoner = FakeReasoner(_complete_plan(missing=("failure_recovery",)), '{"summary":"coverage is incomplete","findings":[],"missing_coverage":[]}')
    report = run(CodexCustomerTester(EvidenceLedger(), reasoner).test(
        CallableAdapter("customer-agent", lambda payload: {"answer": payload["question"]}),
        target={"channel": "callable"},
        customer_goal="客户要得到可用回答",
    ))
    assert report.status == "incomplete"
    assert any(item.dimension == "failure_recovery" and item.status == "missing" for item in report.coverage)


def test_codex_customer_tester_blocks_a_shallow_plan_before_execution():
    shallow = {
        "profile": {"agent_id": "shallow", "purpose": "answer", "output_schema": {"type": "object"}},
        "journeys": [
            {
                "scenario_id": "scenario-repeated_input_or_correction",
                "goal": "generic request",
                "coverage_dimensions": ["repeated_input_or_correction"],
                "steps": [
                    {"step_id": "send", "kind": "user_input", "payload": {"question": "hello"}},
                    {"step_id": "check", "kind": "expect", "assertions": [{"kind": "no_error"}]},
                ],
            }
        ],
        "completeness_checks": [
            {"check_id": "check-repeat", "dimension": "repeated_input_or_correction", "scenario_ids": ["scenario-repeated_input_or_correction"]}
        ],
        "limitations": [],
    }
    reasoner = FakeReasoner(__import__("json").dumps(shallow), '{"summary":"not reached","findings":[],"missing_coverage":[]}')
    ledger = EvidenceLedger()
    report = run(CodexCustomerTester(ledger, reasoner).test(
        CallableAdapter("customer-agent", lambda payload: {"answer": payload["question"]}),
        target={"channel": "callable"},
        customer_goal="客户纠正后重新提交",
    ))
    assert report.status == "blocked"
    assert report.runs == ()
    assert "repeated-input" in (report.error or "")


def test_codex_review_cannot_hide_an_unscoped_finding():
    reasoner = FakeReasoner(
        _complete_plan(),
        '{"summary":"defect","findings":[{"title":"forged","evidence_ids":["not-in-ledger"]}],"missing_coverage":[]}',
    )
    report = run(CodexCustomerTester(EvidenceLedger(), reasoner).test(
        CallableAdapter("customer-agent", lambda payload: {"answer": payload["question"]}),
        target={"channel": "callable"},
        customer_goal="客户要得到可用回答",
    ))
    assert report.status == "fail"
    assert report.review.status == "findings"
    assert report.review.findings == ()
    assert "forged" in report.review.missing_coverage[0]


def test_async_job_bound_is_unknown_and_fixture_environment_resets():
    fixture = FixtureEnvironment()
    fixture.register("balance", {"value": 10})
    fixture.set_runtime("balance", {"value": 0})
    fixture.reset()
    assert fixture.get("balance") == {"value": 10}
    adapter = AsyncJobAdapter("job", lambda payload: "job-1", lambda job_id: RawObservation(status="running"), max_polls=1)
    result = run(CustomerSimulationRunner(EvidenceLedger()).run(
        CustomerJourney("job", "job", (JourneyStep("submit", "user_input", {"q": "x"}),)),
        AgentContractProfile("a", "job"),
        adapter,
    ))
    assert result.status is RunStatus.INCONCLUSIVE
