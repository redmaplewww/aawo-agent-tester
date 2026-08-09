"""Deterministic, evidence-bound customer friction heuristics."""
from __future__ import annotations

from collections import Counter
from typing import Iterable

from .models import Finding, FindingKind, JourneyStep, RawObservation, Severity, digest


def find_friction(run_id: str, steps: Iterable[JourneyStep], observations: Iterable[tuple[str, RawObservation]]) -> tuple[Finding, ...]:
    step_list = tuple(steps)
    observed = tuple(observations)
    findings: list[Finding] = []
    payloads = [step.payload for step in step_list if step.kind == "user_input"]
    counts = Counter(digest(item) for item in payloads)
    repeated = [key for key, count in counts.items() if count > 1]
    if repeated:
        findings.append(Finding(
            finding_id=f"finding_{run_id}_repeat",
            run_id=run_id,
            kind=FindingKind.HUMAN_FRICTION,
            severity=Severity.MEDIUM,
            title="客户旅程重复提交相同输入",
            detail="同一旅程中出现完全相同的用户输入，可能要求客户重复确认或重复填写；需领域专家确认是否有业务理由。",
            evidence_ids=(),
        ))
    for step_id, observation in observed:
        if observation.status == "failed" and observation.error:
            text = observation.error.lower()
            actionable = any(word in text for word in ("retry", "required", "missing", "请", "需要", "重新"))
            if not actionable:
                findings.append(Finding(
                    finding_id=f"finding_{run_id}_{step_id}_error",
                    run_id=run_id,
                    kind=FindingKind.HUMAN_FRICTION,
                    severity=Severity.MEDIUM,
                    title="错误没有可行动的恢复信息",
                    detail="被测 Agent/通道返回失败，但错误文本没有说明原因或下一步动作。",
                    step_id=step_id,
                ))
    return tuple(findings)
