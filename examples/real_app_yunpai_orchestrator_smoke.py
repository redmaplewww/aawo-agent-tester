"""Run read-only journeys against an isolated real Yunpai Orchestrator app."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from httpx import ASGITransport, AsyncClient

from aawo_agent_tester import (
    AgentContractProfile,
    CallableAdapter,
    CustomerJourney,
    CustomerSimulationRunner,
    EvidenceLedger,
    JourneyStep,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path)
    return parser


async def _run_journey(
    *,
    agent_id: str,
    scenario_id: str,
    goal: str,
    output_schema: dict[str, Any],
    steps: tuple[JourneyStep, ...],
    function: Any,
) -> tuple[dict[str, Any], int]:
    ledger = EvidenceLedger()
    profile = AgentContractProfile(
        agent_id=agent_id,
        adapter_id="callable:yunpai-asgi",
        purpose=goal,
        output_schema=output_schema,
    )
    journey = CustomerJourney(
        scenario_id=scenario_id,
        goal=goal,
        actor={"role": "customer_simulation", "environment": "isolated"},
        steps=steps,
    )
    result = await CustomerSimulationRunner(ledger).run(
        journey,
        profile,
        CallableAdapter("callable:yunpai-asgi", function),
    )
    return result.to_dict(), len(ledger.records())


async def _execute() -> dict[str, Any]:
    root = Path(os.environ["YUNPAI_ORCH_ROOT"]).resolve()
    os.environ.setdefault("FEISHU_LONG_CONNECTION_ENABLED", "0")
    os.environ.setdefault("TEAM_AGENT_ADMIN_TOKEN", "isolated-test-token")

    # Import after environment setup so the target's settings are isolated.
    from orchestrator.api import create_app, lifespan  # noqa: PLC0415

    with tempfile.TemporaryDirectory(prefix="yunpai-orchestrator-skill-") as data_dir:
        app = create_app(
            decls_root=root / "orchestrator" / "module_decls",
            enable_memory=False,
            team_agent_db_path=Path(data_dir) / "team-agent.db",
        )
        async with lifespan(app):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://isolated-yunpai-orchestrator",
            ) as client:

                async def health(_payload: object) -> dict[str, Any]:
                    response = await client.get("/health")
                    return {"http_status": response.status_code, "body": response.json()}

                async def security(_payload: object) -> dict[str, Any]:
                    denied = await client.get("/jobs")
                    allowed = await client.get(
                        "/jobs", headers={"X-Team-Agent-Token": "isolated-test-token"}
                    )
                    return {
                        "denied_status": denied.status_code,
                        "allowed_status": allowed.status_code,
                        "allowed_source": allowed.json().get("source"),
                    }

                health_run, health_records = await _run_journey(
                    agent_id="yunpai-orchestrator-isolated",
                    scenario_id="yunpai.orchestrator.isolated.health",
                    goal="确认隔离运行时可完成健康预检",
                    output_schema={
                        "type": "object",
                        "required": ["http_status", "body"],
                    },
                    steps=(
                        JourneyStep("health", "user_input", {}),
                        JourneyStep(
                            "contract",
                            "expect",
                            assertions=(
                                {"kind": "path_equals", "path": "http_status", "value": 200},
                                {"kind": "path_equals", "path": "body.status", "value": "ok"},
                                {
                                    "kind": "path_equals",
                                    "path": "body.module",
                                    "value": "orchestrator",
                                },
                                {
                                    "kind": "path_equals",
                                    "path": "body.agent",
                                    "value": "microsoft-agent-framework",
                                },
                            ),
                        ),
                    ),
                    function=health,
                )
                security_run, security_records = await _run_journey(
                    agent_id="yunpai-orchestrator-isolated-security",
                    scenario_id="yunpai.orchestrator.isolated.auth",
                    goal="确认 Agent 管理接口拒绝匿名访问并允许带管理员令牌的读取",
                    output_schema={
                        "type": "object",
                        "required": ["denied_status", "allowed_status", "allowed_source"],
                    },
                    steps=(
                        JourneyStep("security", "user_input", {}),
                        JourneyStep(
                            "contract",
                            "expect",
                            assertions=(
                                {
                                    "kind": "path_equals",
                                    "path": "denied_status",
                                    "value": 401,
                                },
                                {
                                    "kind": "path_equals",
                                    "path": "allowed_status",
                                    "value": 200,
                                },
                                {
                                    "kind": "path_equals",
                                    "path": "allowed_source",
                                    "value": "in-memory",
                                },
                            ),
                        ),
                    ),
                    function=security,
                )

    return {
        "target": "F:\\opencode\\云湃智算\\云湃一体机\\Yunpai_Project\\yunpai-orchestrator",
        "execution": "isolated real FastAPI lifecycle; memory backends disabled; temporary SQLite",
        "runs": [
            {"status": health_run["status"], "run": health_run, "ledger_records": health_records},
            {"status": security_run["status"], "run": security_run, "ledger_records": security_records},
        ],
        "overall_status": (
            "pass"
            if health_run["status"] == "pass" and security_run["status"] == "pass"
            else "fail"
        ),
        "limitations": [
            "This is not evidence that the deployed port 9000 is running.",
            "Memory backends, Feishu, downstream modules, and external LLM calls were disabled.",
            "No business write or production side effect was exercised.",
        ],
    }


def main() -> None:
    args = _parser().parse_args()
    report = asyncio.run(_execute())
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
