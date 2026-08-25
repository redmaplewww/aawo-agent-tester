from __future__ import annotations

import asyncio
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

from codex_agent_tester import (
    AgentContractProfile,
    CallableAdapter,
    CliAdapter,
    CustomerJourney,
    CustomerSimulationRunner,
    EvidenceLedger,
    HttpAdapter,
    JourneyStep,
    RawObservation,
    RunStatus,
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
            "properties": {"answer": {"type": "string"}, "reference": {"type": "string"}},
        },
    )


def journey(*steps: JourneyStep, side_effect_policy: str = "read_only") -> CustomerJourney:
    return CustomerJourney("customer.question.v1", "客户获得可引用的答案", tuple(steps), side_effect_policy=side_effect_policy)


def test_customer_journey_passes_with_raw_request_and_response_evidence():
    ledger = EvidenceLedger()
    result = run(
        CustomerSimulationRunner(ledger).run(
            journey(
                JourneyStep("ask", "user_input", {"question": "价格"}),
                JourneyStep("verify", "expect", assertions=({"kind": "contains_keys", "keys": ["answer", "reference"]},)),
            ),
            profile(),
            CallableAdapter("callable-1", lambda payload: {"answer": payload["question"], "reference": "kb-1"}),
        )
    )
    assert result.status is RunStatus.PASS
    events = ledger.records(record_type="interaction.event", aggregate_id=result.run_id)
    assert [event["payload"]["direction"] for event in events] == ["request", "response"]


def test_observe_step_calls_adapter_and_records_observation_evidence():
    ledger = EvidenceLedger()
    result = run(
        CustomerSimulationRunner(ledger).run(
            journey(
                JourneyStep("ask", "user_input", {"question": "价格"}),
                JourneyStep("observe", "observe", assertions=({"kind": "contains_keys", "keys": ["answer"]},)),
            ),
            AgentContractProfile("agent-1", "callable-1", output_schema={"type": "object"}),
            CallableAdapter("callable-1", lambda payload: {"answer": payload["question"]}),
        )
    )
    assert result.status is RunStatus.PASS
    assert result.step_results[1].evidence_ids
    events = ledger.records(record_type="interaction.event", aggregate_id=result.run_id)
    assert [event["payload"]["direction"] for event in events] == ["request", "response", "observation"]


def test_missing_output_field_is_fail_and_never_silently_repaired():
    ledger = EvidenceLedger()
    result = run(
        CustomerSimulationRunner(ledger).run(
            journey(JourneyStep("ask", "user_input", {"question": "价格"})),
            profile(),
            CallableAdapter("callable-1", lambda _payload: {"answer": "42"}),
        )
    )
    assert result.status is RunStatus.FAIL
    assert result.step_results[0].assertion_errors == ("$.reference: required field is missing",)
    assert not any(item["payload"].get("status") == "pass" for item in ledger.records(aggregate_id=result.run_id))


def test_unknown_side_effect_result_is_inconclusive_and_stops():
    result = run(
        CustomerSimulationRunner(EvidenceLedger()).run(
            journey(JourneyStep("submit", "user_input", {"action": "charge"}), side_effect_policy="sandbox_write"),
            profile(),
            CallableAdapter("callable-1", lambda _payload: RawObservation(status="unknown", error="unreconciled"), side_effect_policy="sandbox_write"),
        )
    )
    assert result.status is RunStatus.INCONCLUSIVE
    assert result.step_results[0].status.value == "unknown"


def test_read_only_journey_blocks_write_capability_before_adapter_invocation():
    calls = {"count": 0}

    def agent(_payload):
        calls["count"] += 1
        return {"answer": "should not run"}

    result = run(
        CustomerSimulationRunner(EvidenceLedger()).run(
            journey(JourneyStep("ask", "user_input", {"q": "x"})),
            AgentContractProfile("a", "write", output_schema={"type": "object"}),
            CallableAdapter("write", agent, side_effect_policy="sandbox_write"),
        )
    )
    assert result.status is RunStatus.BLOCKED
    assert calls["count"] == 0


def test_http_adapter_uses_real_local_http_contract():
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802 - stdlib handler API
            size = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(size).decode("utf-8"))
            body = json.dumps({"answer": payload["question"], "reference": "local"}).encode()
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
        result = run(
            CustomerSimulationRunner(EvidenceLedger()).run(
                journey(JourneyStep("ask", "user_input", {"question": "HTTP"})),
                profile(),
                HttpAdapter("http-1", f"http://127.0.0.1:{server.server_port}/agent"),
            )
        )
        assert result.status is RunStatus.PASS
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_cli_adapter_uses_explicit_argv_without_shell():
    result = run(
        CustomerSimulationRunner(EvidenceLedger()).run(
            journey(JourneyStep("ask", "user_input", {"question": "CLI"})),
            profile(),
            CliAdapter(
                "cli-1",
                sys.executable,
                ("-c", "import json,sys; p=json.load(sys.stdin); print(json.dumps({'answer':p['question'],'reference':'cli'}))"),
            ),
        )
    )
    assert result.status is RunStatus.PASS
