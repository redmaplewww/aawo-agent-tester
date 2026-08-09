"""Sanitized real-AAWO smoke for the customer-journey test team."""
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
)


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="aawo-agent-test-") as temp_dir:
        root = Path(temp_dir)
        ledger = EvidenceLedger(root / "tester.sqlite3")
        profile = AgentContractProfile(
            "example-agent",
            "example-callable",
            output_schema={
                "type": "object",
                "required": ["answer"],
                "properties": {"answer": {"type": "string"}},
            },
        )
        journey = CustomerJourney(
            "example.customer.read.v1",
            "Customer receives one confirmed answer",
            (
                JourneyStep("ask", "user_input", {"question": "status"}),
                JourneyStep(
                    "verify",
                    "expect",
                    assertions=({"kind": "contains_keys", "keys": ["answer"]},),
                ),
            ),
        )
        adapter = CallableAdapter(
            "example-callable",
            lambda payload: {"answer": f"confirmed:{payload['question']}"},
        )
        try:
            result = await AAWOTestTeamRunner(
                ledger,
                aawo_store_path=root / "aawo.sqlite3",
            ).run(
                journey,
                profile,
                adapter,
                memory_scope="example/project/read-only",
            )
            print(json.dumps({
                "status": result.test_run.status.value,
                "workflow_completed": result.workflow_status["all_completed"],
                "team_member_count": len(result.team_result["members"]),
                "scoped_evidence_count": len(result.evidence_refs),
                "release_count": len(result.release_order),
            }, ensure_ascii=False, sort_keys=True))
        finally:
            ledger.close()


if __name__ == "__main__":
    asyncio.run(main())
