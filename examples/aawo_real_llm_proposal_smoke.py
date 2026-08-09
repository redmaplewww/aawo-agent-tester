"""Run one real LLM proposal through AAWO and reject it without human approval."""
from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path

from aawo_agent_tester import (
    AAWOTestTeamRunner,
    AgentContractProfile,
    CallableAdapter,
    CustomerJourney,
    EvidenceLedger,
    JourneyStep,
    OpenAICompatibleReasoner,
    load_managed_env,
)


async def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    loaded_keys = load_managed_env(project_root / ".env.local")
    if not loaded_keys:
        print(json.dumps({"status": "blocked", "reason": "managed LLM env is not loaded"}, ensure_ascii=False))
        return 2

    with tempfile.TemporaryDirectory(prefix="aawo-real-llm-proposal-") as temp_dir:
        root = Path(temp_dir)
        ledger = EvidenceLedger(root / "tester.sqlite3")
        reasoner = OpenAICompatibleReasoner(timeout=90)
        profile = AgentContractProfile(
            "real-llm-demo-agent",
            "real-llm-demo-callable",
            purpose="return a referenced answer",
            output_schema={
                "type": "object",
                "required": ["answer", "reference"],
                "properties": {
                    "answer": {"type": "string"},
                    "reference": {"type": "string"},
                },
            },
        )
        journey = CustomerJourney(
            "real-llm-demo.v1",
            "客户获得带引用的答案",
            (
                JourneyStep("ask", "user_input", {"question": "交付状态"}),
                JourneyStep(
                    "verify",
                    "expect",
                    assertions=({"kind": "contains_keys", "keys": ["answer", "reference"]},),
                ),
            ),
        )

        def agent(_payload):
            return {"answer": "confirmed", "reference": "customer-system"}

        try:
            result = await AAWOTestTeamRunner(
                ledger,
                aawo_store_path=root / "aawo.sqlite3",
            ).run(
                journey,
                profile,
                CallableAdapter("real-llm-demo-callable", agent),
                memory_scope="real-llm/demo",
                llm_reasoner=reasoner,
                llm_correction="客户要求在最终答案前增加引用完整性检查。",
                evolution_approval=None,
            )
        finally:
            ledger.close()

    proposal = result.llm_proposal
    evolution = result.evolution
    output = {
        "baseline_status": result.test_run.status.value,
        "llm_model": reasoner.model,
        "llm_proposal_status": result.team_result.get("llm_proposal_status"),
        "proposal_kind": proposal.kind if proposal is not None else None,
        "proposal_evidence_count": len(proposal.evidence_ids) if proposal is not None else 0,
        "evolution_status": evolution.status if evolution is not None else None,
        "applied": False,
        "llm_proposal_error": result.llm_proposal_error,
    }
    print(json.dumps(output, ensure_ascii=False, sort_keys=True))
    return 0 if proposal is not None and evolution is not None and evolution.status == "rejected" else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
