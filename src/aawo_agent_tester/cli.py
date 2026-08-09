from __future__ import annotations

import argparse
import asyncio
import json

from .adapters import CallableAdapter
from .ledger import EvidenceLedger
from .models import AgentContractProfile, CustomerJourney, JourneyStep
from .runner import CustomerSimulationRunner


def main() -> int:
    parser = argparse.ArgumentParser(description="AAWO Agent understanding tester")
    parser.add_argument("command", choices=("demo",))
    args = parser.parse_args()
    if args.command == "demo":
        return asyncio.run(_demo())
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


if __name__ == "__main__":
    raise SystemExit(main())
