from __future__ import annotations

import asyncio
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import pytest

from aawo_agent_tester import (
    AgentContractProfile,
    AsyncJobAdapter,
    CallableAdapter,
    Correction,
    CorrectionImpactAnalyzer,
    CustomerJourney,
    CustomerSimulationRunner,
    EvidenceLedger,
    EvolutionGovernor,
    EvolutionProposal,
    FixtureEnvironment,
    JourneyStep,
    OpenAICompatibleReasoner,
    RawObservation,
    ReasoningProviderError,
    ReasoningResponse,
    RunStatus,
    UnderstandingEngine,
    proposal_from_response,
)


def run(coro):
    return asyncio.run(coro)


def test_profile_can_be_reloaded_from_append_only_ledger_after_correction():
    ledger = EvidenceLedger()
    engine = UnderstandingEngine(ledger)
    profile = engine.create_profile(
        "agent-1",
        "callable-1",
        input_schema={"type": "object"},
        output_schema={"type": "string"},
    )
    corrected = engine.apply_correction(
        profile,
        Correction(
            "corr-profile",
            "output_schema",
            {"type": "string"},
            {"type": "object"},
            "客户确认返回结构化对象",
            ("customer-confirmation-1",),
        ),
    )

    reloaded = engine.load_profile("agent-1")
    assert reloaded.revision == corrected.revision
    assert reloaded.output_schema == {"type": "object"}
    assert any(item.status.value == "confirmed" for item in reloaded.hypotheses)
    assert len(ledger.records(aggregate_id="agent-1")) >= 3


def test_correction_impact_selects_minimum_explicit_and_affected_journeys():
    ledger = EvidenceLedger()
    analyzer = CorrectionImpactAnalyzer(ledger)
    journeys = (
        CustomerJourney(
            "journey-a",
            "query",
            (JourneyStep("ask", "user_input", {"question": "a"}),),
        ),
        CustomerJourney(
            "journey-b",
            "query",
            (JourneyStep("ask", "user_input", {"question": "b"}),),
        ),
        CustomerJourney(
            "journey-c",
            "query",
            (JourneyStep("reset", "reset"),),
        ),
    )
    plan = analyzer.plan(
        Correction(
            "corr-output",
            "output_schema",
            {"type": "string"},
            {"type": "object"},
            "output changed",
            (),
            ("journey-b",),
        ),
        journeys,
    )
    assert plan.selected_scenario_ids == ("journey-b",)
    assert "correction_explicit_regression_scope_overrides_inference" in plan.reasons
    assert ledger.get(plan.plan_id)["record_type"] == "regression.plan"


def test_regression_plan_executes_only_selected_scenarios():
    ledger = EvidenceLedger()
    analyzer = CorrectionImpactAnalyzer(ledger)
    runner = CustomerSimulationRunner(ledger)
    profile = AgentContractProfile(
        "agent-1",
        "callable-1",
        output_schema={"type": "object", "required": ["answer"]},
    )
    journeys = (
        CustomerJourney("a", "a", (JourneyStep("ask", "user_input", {"q": "a"}),)),
        CustomerJourney("b", "b", (JourneyStep("ask", "user_input", {"q": "b"}),)),
    )
    plan = analyzer.plan(
        Correction("corr-run", "output_schema", None, None, "changed", (), ("b",)),
        journeys,
    )
    runs = run(
        analyzer.execute(
            plan,
            profile,
            journeys,
            CallableAdapter("callable-1", lambda payload: {"answer": payload["q"]}),
            runner,
        )
    )
    assert [item.scenario_id for item in runs] == ["b"]
    assert ledger.get(f"{plan.plan_id}_completed")["payload"]["run_statuses"] == ["pass"]


def test_reasoning_proposal_parser_is_fail_closed_and_governed():
    response = ReasoningResponse(
        "resp-1",
        "test-model",
        '{"kind":"contract","base_revision":2,"proposed_change":{"path":"output_schema"},"evidence_ids":["ev-1"],"risk":"high"}',
        {},
    )
    proposal = proposal_from_response(response)
    assert isinstance(proposal, EvolutionProposal)
    ledger = EvidenceLedger()
    governor = EvolutionGovernor(ledger)
    governor.submit(proposal)
    with pytest.raises(PermissionError):
        governor.decide(proposal, decision="approved", decided_by="optimizer", reason="model suggested it")
    decision = governor.decide(
        proposal,
        decision="shadow",
        decided_by="operator",
        reason="observe in canary first",
        human_approved=True,
    )
    assert decision.decision == "shadow"


def test_reasoning_parser_rejects_non_object_or_missing_evidence():
    with pytest.raises(ReasoningProviderError):
        proposal_from_response(ReasoningResponse("r", "m", "[]", {}))
    with pytest.raises(ReasoningProviderError):
        proposal_from_response(ReasoningResponse("r", "m", '{"kind":"scenario"}', {}))


def test_reasoner_accepts_llm_skill_generic_environment_aliases(monkeypatch):
    monkeypatch.delenv("AAWO_TESTER_LLM_BASE_URL", raising=False)
    monkeypatch.delenv("AAWO_TESTER_LLM_MODEL", raising=False)
    monkeypatch.delenv("AAWO_TESTER_LLM_API_KEY", raising=False)
    monkeypatch.setenv("LLM_BASE_URL", "http://localhost:9999/v1")
    monkeypatch.setenv("LLM_MODEL", "configured-model")
    monkeypatch.setenv("LLM_API_KEY", "process-only-test-value")
    provider = OpenAICompatibleReasoner()
    assert provider.base_url == "http://localhost:9999/v1"
    assert provider.model == "configured-model"


def test_reasoner_proposal_enforces_kind_revision_and_evidence_scope():
    class StubReasoner(OpenAICompatibleReasoner):
        def __init__(self):
            self.model = "stub"

        async def complete(self, messages, *, response_schema=None):
            assert messages[0]["role"] == "system"
            assert response_schema is not None
            return ReasoningResponse(
                "stub-response",
                "stub",
                '{"kind":"workflow","base_revision":1,"proposed_change":{"add_step":"verify"},"evidence_ids":["ev-1"],"risk":"low"}',
                {},
            )

    proposal = run(
        StubReasoner().propose_evolution(
            agent_id="agent",
            kind="workflow",
            base_revision=1,
            contract={"output": {"required": ["answer"]}},
            journey={"steps": ["ask", "check"]},
            evidence=({"evidence_id": "ev-1", "summary": "observed correction"},),
        )
    )
    assert proposal.proposed_change == {"add_step": "verify"}

    class OutOfScopeReasoner(StubReasoner):
        async def complete(self, messages, *, response_schema=None):
            return ReasoningResponse(
                "stub-response",
                "stub",
                '{"kind":"workflow","base_revision":1,"proposed_change":{},"evidence_ids":["ev-secret"],"risk":"low"}',
                {},
            )

    with pytest.raises(ReasoningProviderError, match="outside the supplied scope"):
        run(
            OutOfScopeReasoner().propose_evolution(
                agent_id="agent",
                kind="workflow",
                base_revision=1,
                contract={},
                journey={},
                evidence=({"evidence_id": "ev-1", "summary": "observed"},),
            )
        )


def test_reasoner_performs_one_bounded_correction_retry():
    class RetryReasoner(OpenAICompatibleReasoner):
        def __init__(self):
            self.model = "stub"
            self.calls = 0

        async def complete(self, messages, *, response_schema=None):
            self.calls += 1
            if self.calls == 1:
                return ReasoningResponse(
                    "bad-response",
                    "stub",
                    '{"kind":"workflow","base_revision":1,"proposed_change":"prose","evidence_ids":["ev-1"],"risk":"medium"}',
                    {},
                )
            return ReasoningResponse(
                "good-response",
                "stub",
                '{"kind":"workflow","base_revision":1,"proposed_change":{"add_step":"verify"},"evidence_ids":["ev-1"],"risk":"low"}',
                {},
            )

    reasoner = RetryReasoner()
    proposal = run(
        reasoner.propose_evolution(
            agent_id="agent",
            kind="workflow",
            base_revision=1,
            contract={},
            journey={},
            evidence=({"evidence_id": "ev-1", "summary": "observed"},),
        )
    )
    assert reasoner.calls == 2
    assert proposal.proposed_change == {"add_step": "verify"}


def test_openai_compatible_reasoner_uses_local_protocol_without_external_network():
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            size = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(size).decode("utf-8"))
            assert payload["model"] == "local-test"
            body = json.dumps(
                {
                    "id": "local-response",
                    "model": "local-test",
                    "choices": [
                        {
                            "message": {
                                "content": '{"kind":"scenario","base_revision":1,"proposed_change":{"scenario_id":"x"},"evidence_ids":["ev-local"]}'
                            }
                        }
                    ],
                }
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        provider = OpenAICompatibleReasoner(
            base_url=f"http://127.0.0.1:{server.server_port}",
            model="local-test",
            api_key="process-only-secret",
        )
        response = run(provider.complete(({"role": "user", "content": "propose"},)))
        proposal = proposal_from_response(response)
        assert proposal.kind == "scenario"
        assert response.response_id == "local-response"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_async_job_adapter_waits_for_terminal_observation_without_implicit_cancel():
    states = {"polls": 0}

    def submit(payload):
        return "job-1"

    def poll(job_id):
        states["polls"] += 1
        if states["polls"] < 2:
            return RawObservation(status="running")
        return RawObservation(output={"answer": "done"})

    result = run(
        CustomerSimulationRunner(EvidenceLedger()).run(
            CustomerJourney("job", "job", (JourneyStep("submit", "user_input", {"q": "x"}),)),
            AgentContractProfile("a", "job", output_schema={"type": "object", "required": ["answer"]}),
            AsyncJobAdapter("job", submit, poll),
        )
    )
    assert result.status is RunStatus.PASS
    assert states["polls"] == 2


def test_async_job_bound_is_unknown_and_fixture_environment_resets():
    fixture = FixtureEnvironment()
    fixture.register("balance", {"value": 10})
    fixture.set_runtime("balance", {"value": 0})
    assert fixture.get("balance") == {"value": 0}
    fixture.reset()
    assert fixture.get("balance") == {"value": 10}

    adapter = AsyncJobAdapter("job", lambda payload: "job-1", lambda job_id: RawObservation(status="running"), max_polls=1)
    result = run(
        CustomerSimulationRunner(EvidenceLedger()).run(
            CustomerJourney("job", "job", (JourneyStep("submit", "user_input", {"q": "x"}),)),
            AgentContractProfile("a", "job"),
            adapter,
        )
    )
    assert result.status is RunStatus.INCONCLUSIVE


def test_read_only_journey_blocks_write_capability_before_adapter_invocation():
    calls = {"count": 0}

    def agent(payload):
        calls["count"] += 1
        return {"answer": "should not run"}

    result = run(
        CustomerSimulationRunner(EvidenceLedger()).run(
            CustomerJourney("read", "read", (JourneyStep("ask", "user_input", {"q": "x"}),), side_effect_policy="read_only"),
            AgentContractProfile("a", "write", output_schema={"type": "object"}),
            CallableAdapter("write", agent, side_effect_policy="sandbox_write"),
        )
    )
    assert result.status is RunStatus.BLOCKED
    assert calls["count"] == 0
