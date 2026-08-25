from __future__ import annotations

import argparse
import asyncio
import json

from .adapters import CallableAdapter
from .ledger import EvidenceLedger
from .models import AgentContractProfile, CustomerJourney, JourneyStep
from .runner import CustomerSimulationRunner


def main() -> int:
    parser = argparse.ArgumentParser(description="Codex Agent customer-simulation tester")
    parser.add_argument("command", choices=("demo", "codex-status"))
    args = parser.parse_args()
    if args.command == "demo":
        return asyncio.run(_demo())
    if args.command == "codex-status":
        return _codex_status()
    return 2


async def _demo() -> int:
    def agent(payload: dict[str, object]) -> dict[str, object]:
        return {"answer": f"processed:{payload['question']}", "trace_id": "demo"}

    ledger = EvidenceLedger(":memory:")
    adapter = CallableAdapter("demo-callable", agent)
    profile = AgentContractProfile("demo-agent", "demo-callable", output_schema={
        "type": "object",
        "required": ["answer", "trace_id"],
        "properties": {"answer": {"type": "string"}, "trace_id": {"type": "string"}},
    })
    journey = CustomerJourney("demo.v1", "客户获得处理结果", (
        JourneyStep("ask", "user_input", {"question": "hello"}),
        JourneyStep("check", "expect", assertions=({"kind": "contains_keys", "keys": ["answer", "trace_id"]},)),
    ))
    run = await CustomerSimulationRunner(ledger).run(journey, profile, adapter)
    print(json.dumps(run.to_dict(), ensure_ascii=False, indent=2))
    return 0 if run.status.value == "pass" else 1


def _codex_status() -> int:
    """Verify the SDK/runtime boundary without printing account or token data."""
    try:
        from openai_codex import ApprovalMode, Codex, Sandbox

        codex = Codex()
        try:
            thread = codex.thread_start(
                approval_mode=ApprovalMode.deny_all,
                sandbox=Sandbox.read_only,
                ephemeral=True,
                base_instructions="Read-only status probe; do not edit files or call the target Agent.",
            )
            metadata = getattr(codex, "metadata", None)
            version = getattr(metadata, "version", None)
            print(json.dumps({
                "status": "ready",
                "sdk": "openai-codex",
                "runtime_version": version,
                "thread_started": thread is not None,
                "turn_executed": False,
            }, ensure_ascii=False))
        finally:
            close = getattr(codex, "close", None)
            if callable(close):
                close()
        return 0
    except Exception as exc:
        print(json.dumps({"status": "blocked", "sdk": "openai-codex", "error_type": type(exc).__name__}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
