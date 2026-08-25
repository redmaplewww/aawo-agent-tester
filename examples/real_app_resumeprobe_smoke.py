"""Read-only smoke test against the local ResumeProbe FastAPI application.

Run from this project with ``RESUMEPROBE_ROOT`` pointing at the application
checkout. The app is imported as a real FastAPI application, while its data
directory is isolated by the caller.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from codex_agent_tester import (
    AgentContractProfile,
    CallableAdapter,
    CustomerJourney,
    CustomerSimulationRunner,
    EvidenceLedger,
    JourneyStep,
)


def main() -> None:
    app_root = Path(os.environ["RESUMEPROBE_ROOT"]).resolve()
    sys.path.insert(0, str(app_root))
    from web_app import app  # noqa: PLC0415 - target application boundary

    client = TestClient(app)

    def health(_payload: object) -> dict:
        response = client.get("/api/health")
        return {"http_status": response.status_code, "body": response.json()}

    async def run() -> dict:
        ledger = EvidenceLedger()
        profile = AgentContractProfile(
            agent_id="resumeprobe-web-health",
            adapter_id="resumeprobe-web",
            input_schema={"type": "object"},
            output_schema={"type": "object", "required": ["http_status", "body"]},
        )
        journey = CustomerJourney(
            scenario_id="resumeprobe.health.read_only",
            goal="确认服务健康状态可被操作员读取",
            actor={"role": "operator", "purpose": "health preflight"},
            steps=(
                JourneyStep("health", "user_input", {"probe": "health"}),
                JourneyStep(
                    "contract",
                    "expect",
                    assertions=(
                        {"kind": "contains_keys", "keys": ["http_status", "body"]},
                    ),
                ),
                JourneyStep(
                    "status",
                    "expect",
                    assertions=({"kind": "text_contains", "text": "ok"},),
                ),
            ),
        )
        result = await CustomerSimulationRunner(ledger).run(
            journey, profile, CallableAdapter("resumeprobe-web", health)
        )
        return {
            "status": result.status.value,
            "run_id": result.run_id,
            "step_statuses": [step.status.value for step in result.step_results],
            "finding_ids": list(result.finding_ids),
            "ledger_records": len(ledger.records()),
            "health": health({}),
        }

    print(json.dumps(asyncio.run(run()), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
