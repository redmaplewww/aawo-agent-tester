"""Run a pass and a contract-failure customer journey with no network calls."""
from __future__ import annotations

import asyncio
import json

from codex_agent_tester import AgentContractProfile, CallableAdapter, CustomerJourney, CustomerSimulationRunner, EvidenceLedger, JourneyStep


async def main() -> None:
    ledger = EvidenceLedger("p0_demo.sqlite3")

    def customer_agent(payload: dict[str, str]) -> dict[str, str]:
        return {"answer": f"已处理：{payload['question']}", "reference": "fixture-kb-1"}

    profile = AgentContractProfile(
        "demo-agent",
        "demo-adapter",
        purpose="回答客户问题并给出引用",
        output_schema={
            "type": "object",
            "required": ["answer", "reference"],
            "properties": {"answer": {"type": "string"}, "reference": {"type": "string"}},
        },
    )
    scenario = CustomerJourney("demo.customer-question.v1", "客户获得有引用的回答", (
        JourneyStep("ask", "user_input", {"question": "如何申请售后？"}),
        JourneyStep("check", "expect", assertions=({"kind": "contains_keys", "keys": ["answer", "reference"]},)),
    ))
    result = await CustomerSimulationRunner(ledger).run(scenario, profile, CallableAdapter("demo-adapter", customer_agent))
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    print(f"ledger records: {len(ledger.records())}")


if __name__ == "__main__":
    asyncio.run(main())
