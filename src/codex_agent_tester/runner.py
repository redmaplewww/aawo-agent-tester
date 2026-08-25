"""Customer journey runner with fail-closed result settlement."""
from __future__ import annotations

import uuid
from typing import Any

from .adapters import SessionContext, UnderTestAdapter
from .friction import find_friction
from .ledger import EvidenceLedger
from .models import (
    AgentContractProfile,
    CustomerJourney,
    Finding,
    FindingKind,
    InteractionEvent,
    RawObservation,
    RunStatus,
    Severity,
    StepResult,
    StepStatus,
    TestRun,
    digest,
    utc_now,
)
from .schema import validate


class CustomerSimulationRunner:
    def __init__(self, ledger: EvidenceLedger) -> None:
        self.ledger = ledger

    async def run(self, journey: CustomerJourney, profile: AgentContractProfile, adapter: UnderTestAdapter) -> TestRun:
        run_id = f"run_{uuid.uuid4().hex}"
        self.ledger.append(run_id, "test_run.created", run_id, {
            "run_id": run_id,
            "scenario_id": journey.scenario_id,
            "agent_id": profile.agent_id,
            "profile_revision": profile.revision,
            "status": RunStatus.PLANNED.value,
            "adapter": adapter.describe().__dict__,
        })
        if not side_effect_allowed(journey.side_effect_policy, adapter.describe().side_effect_policy):
            finding = self._finding(
                run_id,
                None,
                FindingKind.SECURITY_RISK,
                Severity.HIGH,
                "场景副作用策略不足以容纳适配器",
                f"journey={journey.side_effect_policy}, adapter={adapter.describe().side_effect_policy}",
            )
            self.ledger.append(finding.finding_id, "finding.created", run_id, finding.to_dict())
            run = TestRun(
                run_id,
                journey.scenario_id,
                profile.agent_id,
                profile.revision,
                RunStatus.BLOCKED,
                finding_ids=(finding.finding_id,),
                finished_at=utc_now(),
            )
            self.ledger.append(f"{run_id}_settled", "test_run.status", run_id, run.to_dict())
            return run
        session = await adapter.open_session(SessionContext(run_id, journey.actor))
        results: list[StepResult] = []
        findings: list[Finding] = []
        observations: list[tuple[str, RawObservation]] = []
        status = RunStatus.PASS
        try:
            self.ledger.append(f"{run_id}_started", "test_run.status", run_id, {"status": RunStatus.RUNNING.value})
            for step in journey.steps:
                if step.kind == "reset":
                    await adapter.reset(session)
                    results.append(StepResult(step.step_id, StepStatus.SETTLED))
                    continue
                if step.kind == "user_input":
                    observation = await adapter.send(session, step.payload)
                    observations.append((step.step_id, observation))
                    request_event_id = self._record_event(run_id, step.step_id, "request", step.payload)
                    response_event_id = self._record_event(run_id, step.step_id, "response", observation.to_dict())
                    evidence_ids = (request_event_id, response_event_id)
                    if observation.is_unknown:
                        result = StepResult(step.step_id, StepStatus.UNKNOWN, observation, evidence_ids=evidence_ids)
                        results.append(result)
                        status = RunStatus.INCONCLUSIVE
                        findings.append(self._finding(run_id, step.step_id, FindingKind.ADAPTER_ERROR, Severity.HIGH, "结果未知，禁止继续放行", observation.error or "adapter returned unknown"))
                        break
                    if observation.is_blocked:
                        result = StepResult(step.step_id, StepStatus.BLOCKED, observation, evidence_ids=evidence_ids)
                        results.append(result)
                        status = RunStatus.BLOCKED
                        findings.append(self._finding(run_id, step.step_id, FindingKind.ADAPTER_ERROR, Severity.MEDIUM, "测试被环境或审批门禁阻塞", observation.error or "adapter blocked"))
                        break
                    if observation.status != "ok":
                        result = StepResult(step.step_id, StepStatus.FAILED, observation, evidence_ids=evidence_ids)
                        results.append(result)
                        status = RunStatus.FAIL
                        findings.append(self._finding(run_id, step.step_id, FindingKind.ADAPTER_ERROR, Severity.HIGH, "被测 Agent 或适配器返回失败", observation.error or observation.status))
                        break
                    errors = validate(observation.output, profile.output_schema)
                    if errors:
                        result = StepResult(step.step_id, StepStatus.FAILED, observation, errors, evidence_ids)
                        results.append(result)
                        status = RunStatus.FAIL
                        findings.append(self._finding(run_id, step.step_id, FindingKind.CONTRACT_VIOLATION, Severity.HIGH, "输出契约不满足", "; ".join(errors)))
                        break
                    results.append(StepResult(step.step_id, StepStatus.OBSERVED, observation, evidence_ids=evidence_ids))
                    continue
                if step.kind == "observe":
                    fresh = await adapter.observe(session)
                    if not fresh:
                        observation = RawObservation(status="unknown", error="adapter returned no observation")
                        observation_event_id = self._record_event(
                            run_id, step.step_id, "observation", observation.to_dict()
                        )
                        observations.append((step.step_id, observation))
                        results.append(
                            StepResult(
                                step.step_id,
                                StepStatus.UNKNOWN,
                                observation,
                                evidence_ids=(observation_event_id,),
                            )
                        )
                        status = RunStatus.INCONCLUSIVE
                        findings.append(
                            self._finding(
                                run_id,
                                step.step_id,
                                FindingKind.ADAPTER_ERROR,
                                Severity.HIGH,
                                "观察步骤没有得到结果",
                                "adapter returned no observation",
                            )
                        )
                        break
                    last = fresh[-1]
                    observation_event_id = self._record_event(
                        run_id, step.step_id, "observation", last.to_dict()
                    )
                    observations.append((step.step_id, last))
                    errors = _assert_observation(last, step.assertions)
                    if errors:
                        results.append(
                            StepResult(
                                step.step_id,
                                StepStatus.FAILED,
                                last,
                                errors,
                                (observation_event_id,),
                            )
                        )
                        status = RunStatus.FAIL
                        findings.append(
                            self._finding(
                                run_id,
                                step.step_id,
                                FindingKind.OUTCOME_FAILURE,
                                Severity.HIGH,
                                "客户观察结果断言失败",
                                "; ".join(errors),
                            )
                        )
                        break
                    results.append(
                        StepResult(
                            step.step_id,
                            StepStatus.VALIDATED,
                            last,
                            evidence_ids=(observation_event_id,),
                        )
                    )
                    continue
                if step.kind == "expect":
                    last = observations[-1][1] if observations else None
                    errors = _assert_observation(last, step.assertions)
                    if errors:
                        results.append(StepResult(step.step_id, StepStatus.FAILED, last, errors))
                        status = RunStatus.FAIL
                        findings.append(self._finding(run_id, step.step_id, FindingKind.OUTCOME_FAILURE, Severity.HIGH, "客户旅程结果断言失败", "; ".join(errors)))
                        break
                    results.append(StepResult(step.step_id, StepStatus.VALIDATED, last))
                    continue
            if status is RunStatus.PASS and len(results) != len(journey.steps):
                status = RunStatus.BLOCKED
        except Exception as exc:
            status = RunStatus.FAIL
            findings.append(self._finding(run_id, None, FindingKind.ADAPTER_ERROR, Severity.CRITICAL, "测试执行器发生未预期异常", f"{type(exc).__name__}: {exc}"))
        finally:
            await adapter.close(session)
        findings.extend(find_friction(run_id, journey.steps, observations))
        for finding in findings:
            self.ledger.append(finding.finding_id, "finding.created", run_id, finding.to_dict())
        run = TestRun(run_id, journey.scenario_id, profile.agent_id, profile.revision, status, tuple(results), tuple(item.finding_id for item in findings), finished_at=utc_now())
        self.ledger.append(f"{run_id}_settled", "test_run.status", run_id, run.to_dict())
        return run

    def _record_event(self, run_id: str, step_id: str, direction: str, payload: Any) -> str:
        event_id = f"event_{uuid.uuid4().hex}"
        event = InteractionEvent(event_id, run_id, step_id, direction, payload, digest(payload))
        self.ledger.append(event_id, "interaction.event", run_id, event.to_dict())
        return event_id

    @staticmethod
    def _finding(run_id: str, step_id: str | None, kind: FindingKind, severity: Severity, title: str, detail: str) -> Finding:
        suffix = step_id or "run"
        return Finding(f"finding_{run_id}_{suffix}_{uuid.uuid4().hex[:8]}", run_id, kind, severity, title, detail, step_id)


def _assert_observation(observation: RawObservation | None, assertions: tuple[dict[str, Any], ...]) -> tuple[str, ...]:
    if observation is None:
        return ("$: no observation is available",)
    errors: list[str] = []
    for assertion in assertions:
        kind = assertion.get("kind")
        if kind == "contains_keys":
            if not isinstance(observation.output, dict):
                errors.append("output is not an object")
            else:
                for key in assertion.get("keys", ()):
                    if key not in observation.output:
                        errors.append(f"missing expected key: {key}")
        elif kind == "text_contains":
            if str(assertion.get("text", "")) not in str(observation.output):
                errors.append(f"text does not contain {assertion.get('text')!r}")
        elif kind == "status_is":
            if observation.status != assertion.get("status"):
                errors.append(f"status expected {assertion.get('status')!r}, got {observation.status!r}")
        elif kind == "path_equals":
            current: Any = observation.output
            path = str(assertion.get("path", ""))
            for part in path.split(".") if path else ():
                if isinstance(current, dict) and part in current:
                    current = current[part]
                    continue
                if isinstance(current, list) and part.isdigit() and int(part) < len(current):
                    current = current[int(part)]
                    continue
                else:
                    errors.append(f"missing expected path: {path}")
                    current = _MISSING
                    break
            if current is not _MISSING and current != assertion.get("value"):
                errors.append(f"path {path!r} expected {assertion.get('value')!r}, got {current!r}")
        elif kind == "no_error":
            if observation.error:
                errors.append(f"unexpected error: {observation.error}")
        else:
            errors.append(f"unsupported assertion kind: {kind!r}")
    return tuple(errors)


_MISSING = object()


def side_effect_allowed(journey_policy: str, adapter_policy: str) -> bool:
    """Return whether the journey explicitly contains the adapter's effects."""
    levels = {"read_only": 0, "sandbox_write": 1, "human_approved_write": 2}
    return levels.get(adapter_policy, 99) <= levels.get(journey_policy, -1)
