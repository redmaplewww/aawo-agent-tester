from __future__ import annotations

import asyncio
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
import sys

import pytest

from aawo_agent_tester import (
    AgentContractProfile,
    CallableAdapter,
    Correction,
    CustomerJourney,
    CustomerSimulationRunner,
    EvidenceLedger,
    FactStatus,
    JourneyStep,
    RawObservation,
    RunStatus,
    UnderstandingEngine,
    build_aawo_department_dict,
    default_test_blueprints,
    register_with_aawo,
    HttpAdapter,
    CliAdapter,
)


def run(coro):
    return asyncio.run(coro)


def profile() -> AgentContractProfile:
    return AgentContractProfile(
        "agent-1",
        "callable-1",
        purpose="answer a customer question",
        output_schema={
            "type": "object",
            "required": ["answer", "reference"],
            "properties": {
                "answer": {"type": "string"},
                "reference": {"type": "string"},
            },
        },
    )


def journey(*steps: JourneyStep, side_effect_policy: str = "read_only") -> CustomerJourney:
    return CustomerJourney(
        "customer.question.v1",
        "客户获得可引用的答案",
        tuple(steps),
        source="customer_trace",
        side_effect_policy=side_effect_policy,
    )


def test_customer_journey_passes_with_raw_request_and_response_evidence():
    def agent(payload):
        return {"answer": f"answer:{payload['question']}", "reference": "kb-1"}

    ledger = EvidenceLedger()
    result = run(CustomerSimulationRunner(ledger).run(
        journey(
            JourneyStep("ask", "user_input", {"question": "价格"}),
            JourneyStep("verify", "expect", assertions=({"kind": "contains_keys", "keys": ["answer", "reference"]},)),
        ),
        profile(),
        CallableAdapter("callable-1", agent),
    ))

    assert result.status is RunStatus.PASS
    events = ledger.records(record_type="interaction.event", aggregate_id=result.run_id)
    assert [event["payload"]["direction"] for event in events] == ["request", "response"]
    assert len(ledger.records(record_type="test_run.status", aggregate_id=result.run_id)) == 2


def test_missing_output_field_is_fail_and_never_silently_repaired():
    ledger = EvidenceLedger()
    result = run(CustomerSimulationRunner(ledger).run(
        journey(JourneyStep("ask", "user_input", {"question": "价格"})),
        profile(),
        CallableAdapter("callable-1", lambda payload: {"answer": "42"}),
    ))

    assert result.status is RunStatus.FAIL
    assert result.step_results[0].assertion_errors == ("$.reference: required field is missing",)
    findings = ledger.records(record_type="finding.created", aggregate_id=result.run_id)
    assert findings[0]["payload"]["kind"] == "contract_violation"
    assert not any(item["payload"].get("status") == "pass" for item in ledger.records(aggregate_id=result.run_id))


def test_unknown_side_effect_result_is_inconclusive_and_stops():
    def agent(payload):
        return RawObservation(status="unknown", error="write result cannot be reconciled")

    ledger = EvidenceLedger()
    result = run(CustomerSimulationRunner(ledger).run(
        journey(
            JourneyStep("submit", "user_input", {"action": "charge"}),
            JourneyStep("must_not_run", "expect", assertions=({"kind": "no_error"},)),
            side_effect_policy="sandbox_write",
        ),
        profile(),
        CallableAdapter("callable-1", agent, side_effect_policy="sandbox_write"),
    ))

    assert result.status is RunStatus.INCONCLUSIVE
    assert [step.step_id for step in result.step_results] == ["submit"]
    assert result.step_results[0].status.value == "unknown"


def test_blocked_result_is_not_a_pass():
    ledger = EvidenceLedger()
    result = run(CustomerSimulationRunner(ledger).run(
        journey(JourneyStep("ask", "user_input", {"question": "secret"})),
        profile(),
        CallableAdapter("callable-1", lambda payload: RawObservation(status="blocked", error="approval_required")),
    ))
    assert result.status is RunStatus.BLOCKED


def test_correction_supersedes_old_hypothesis_and_keeps_history():
    ledger = EvidenceLedger()
    engine = UnderstandingEngine(ledger)
    current = engine.create_profile("agent-1", "callable-1", output_schema={"type": "object"}, source="operator")
    corrected = engine.apply_correction(current, Correction(
        "corr-1", "output_schema", {"type": "object"}, {"type": "string"},
        "客户实际返回纯文本", ("evidence-customer-1",), ("customer.question.v1",),
    ))

    assert corrected.revision == current.revision + 1
    assert any(item.status is FactStatus.SUPERSEDED for item in corrected.hypotheses)
    assert any(item.status is FactStatus.CONFIRMED for item in corrected.hypotheses)
    assert ledger.get("corr-1") is not None
    assert len(ledger.records(record_type="profile.corrected", aggregate_id="agent-1")) == 1


def test_ledger_rejects_same_id_with_different_content():
    ledger = EvidenceLedger()
    ledger.append("r1", "test", "a", {"value": 1})
    with pytest.raises(ValueError):
        ledger.append("r1", "test", "a", {"value": 2})


def test_aawo_blueprints_are_capability_descriptors_not_workflow_nodes():
    blueprints = default_test_blueprints()
    assert {item.blueprint_id for item in blueprints} >= {"test-director", "customer-simulator", "quality-evolution"}
    assert all(item.to_department_blueprint()["executor"] == "aawo_agent_tester" for item in blueprints)


def test_aawo_bridge_uses_public_department_registration_boundary():
    class FakePool:
        def __init__(self):
            self.registered = []

        def register_department(self, spec):
            self.registered.append(spec)

    pool = FakePool()
    department = register_with_aawo(pool)
    assert pool.registered == [department]
    assert department == build_aawo_department_dict()
    assert len(department["blueprints"]) >= 8


def test_http_adapter_uses_real_local_http_contract():
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802 - stdlib handler API
            size = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(size).decode("utf-8"))
            body = json.dumps({"answer": payload["question"], "reference": "local-http"}).encode("utf-8")
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
        ledger = EvidenceLedger()
        result = run(CustomerSimulationRunner(ledger).run(
            journey(
                JourneyStep("ask", "user_input", {"question": "HTTP"}),
                JourneyStep("verify", "expect", assertions=({"kind": "contains_keys", "keys": ["answer", "reference"]},)),
            ),
            profile(),
            HttpAdapter("http-1", f"http://127.0.0.1:{server.server_port}/agent"),
        ))
        assert result.status is RunStatus.PASS
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_http_adapter_supports_explicit_read_only_get():
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 - stdlib handler API
            body = b'{"status":"ok","configured":false}'
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
        observation = run(
            HttpAdapter(
                "http-get-1",
                f"http://127.0.0.1:{server.server_port}/health",
                method="GET",
            ).send(
                {"last": None},
                {"ignored": True},
            )
        )
        assert observation.status == "ok"
        assert observation.output["status"] == "ok"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_structured_path_assertion_does_not_depend_on_string_formatting():
    ledger = EvidenceLedger()
    result = run(
        CustomerSimulationRunner(ledger).run(
            journey(
                JourneyStep("ask", "user_input", {"question": "structured"}),
                JourneyStep(
                    "verify",
                    "expect",
                        assertions=(
                            {"kind": "path_equals", "path": "ok", "value": True},
                            {"kind": "path_equals", "path": "nested.answer", "value": 42},
                            {"kind": "path_equals", "path": "items.0.status", "value": "ready"},
                        ),
                ),
            ),
            profile(),
            CallableAdapter(
                "structured",
                lambda _payload: {
                    "answer": "structured",
                    "reference": "fixture",
                    "ok": True,
                    "nested": {"answer": 42},
                    "items": [{"status": "ready"}],
                },
            ),
        )
    )
    assert result.status is RunStatus.PASS


def test_cli_adapter_uses_explicit_argv_without_shell():
    ledger = EvidenceLedger()
    result = run(CustomerSimulationRunner(ledger).run(
        journey(JourneyStep("ask", "user_input", {"question": "CLI"})),
        profile(),
        CliAdapter(
            "cli-1",
            sys.executable,
            ("-c", "import json,sys; p=json.load(sys.stdin); print(json.dumps({'answer':p['question'],'reference':'cli'}))"),
        ),
    ))
    assert result.status is RunStatus.PASS
