"""Sanitized AAWO supervised workflow-evolution smoke."""
from __future__ import annotations

import asyncio
import copy
import json
import tempfile
from pathlib import Path

from aawo_agent_tester import (
    AAWOTestTeamRunner,
    AgentContractProfile,
    CallableAdapter,
    CustomerJourney,
    EvidenceLedger,
    EvolutionApproval,
    EvolutionProposal,
    JourneyStep,
    journey_to_aawo_workflow_data,
)


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="aawo-agent-evolution-") as temp_dir:
        root = Path(temp_dir)
        ledger = EvidenceLedger(root / "tester.sqlite3")
        journey = CustomerJourney(
            "example.customer.evolution.v1",
            "Customer receives one referenced answer",
            (
                JourneyStep("ask", "user_input", {"question": "status"}),
                JourneyStep(
                    "verify",
                    "expect",
                    assertions=({
                        "kind": "contains_keys",
                        "keys": ["answer", "reference"],
                    },),
                ),
            ),
            evidence_ids=("example-customer-trace",),
        )
        profile = AgentContractProfile(
            "example-evolution-agent",
            "example-evolution-callable",
            output_schema={
                "type": "object",
                "required": ["answer", "reference"],
                "properties": {
                    "answer": {"type": "string"},
                    "reference": {"type": "string"},
                },
            },
        )
        correction_id = "example-evolution-correction"
        ledger.append(
            correction_id,
            "correction.created",
            "example-evolution-proposal",
            {
                "target": "workflow.acceptance",
                "reason": "Require a fresh recovery-path canary.",
            },
        )
        definition = copy.deepcopy(
            journey_to_aawo_workflow_data(journey)["definition"]
        )
        definition["work_nodes"][0]["objective"] += (
            " Re-run the customer journey as a fresh canary."
        )
        proposal = EvolutionProposal(
            "example-evolution-proposal",
            "workflow",
            1,
            {"definition": definition},
            (correction_id,),
            risk="high",
        )
        calls = 0

        def stable_agent(payload):
            nonlocal calls
            calls += 1
            return {
                "answer": f"confirmed:{payload['question']}",
                "reference": "example-system",
            }

        try:
            result = await AAWOTestTeamRunner(
                ledger,
                aawo_store_path=root / "aawo.sqlite3",
            ).run(
                journey,
                profile,
                CallableAdapter("example-evolution-callable", stable_agent),
                memory_scope="example/project/evolution",
                evolution_proposal=proposal,
                evolution_approval=EvolutionApproval(
                    True,
                    "example-human-quality-owner",
                    "Approve one supervised customer-like canary.",
                    human_approved=True,
                ),
            )
            evolution = result.evolution
            assert evolution is not None
            print(json.dumps({
                "adapter_calls": calls,
                "baseline_status": result.test_run.status.value,
                "canary_status": (
                    evolution.canary_run.status.value
                    if evolution.canary_run is not None
                    else None
                ),
                "evolution_status": evolution.status,
                "final_workflow_revision": evolution.final_workflow_revision,
                "rolled_back": evolution.rolled_back,
                "scoped_evidence_count": len(result.evidence_refs),
            }, ensure_ascii=False, sort_keys=True))
        finally:
            ledger.close()


if __name__ == "__main__":
    asyncio.run(main())
