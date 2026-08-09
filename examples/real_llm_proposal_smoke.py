"""Make one real, proposal-only LLM call using the managed local profile."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from aawo_agent_tester import (
    OpenAICompatibleReasoner,
    ReasoningProviderError,
    load_managed_env,
)


async def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    loaded_keys = load_managed_env(project_root / ".env.local")
    if not loaded_keys:
        print(json.dumps({"status": "blocked", "reason": "managed LLM env is not loaded"}, ensure_ascii=False))
        return 2

    reasoner = OpenAICompatibleReasoner(timeout=90)
    try:
        proposal = await reasoner.propose_evolution(
            agent_id="demo-arbitrary-domain-agent",
            kind="workflow",
            base_revision=1,
            contract={
                "input": {"type": "object", "required": ["question"]},
                "output": {"type": "object", "required": ["answer", "confidence"]},
            },
            journey={
                "goal": "客户提交问题并获得可解释答案",
                "steps": [
                    {"id": "submit", "action": "send question"},
                    {"id": "verify", "action": "check answer and confidence"},
                ],
            },
            evidence=(
                {
                    "evidence_id": "ev-demo-001",
                    "summary": "客户纠正：答案必须同时包含可读结论和置信度",
                    "observed_status": "fail",
                },
                {
                    "evidence_id": "ev-demo-002",
                    "summary": "当前 journey 没有单独验证 confidence 字段",
                    "observed_status": "pass",
                },
            ),
            correction="客户要求把 confidence 校验作为提交后必经步骤，并保留失败证据。",
        )
    except (ReasoningProviderError, ValueError, OSError) as exc:
        print(
            json.dumps(
                {"status": "inconclusive", "error_type": type(exc).__name__, "detail": str(exc)},
                ensure_ascii=False,
            )
        )
        return 1

    print(
        json.dumps(
            {
                "status": "proposal_received",
                "model": reasoner.model,
                "proposal_id": proposal.proposal_id,
                "kind": proposal.kind,
                "base_revision": proposal.base_revision,
                "risk": proposal.risk,
                "evidence_ids": list(proposal.evidence_ids),
                "proposed_change": proposal.proposed_change,
                "applied": False,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
