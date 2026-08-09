"""Stable, serializable contracts for the Agent-under-test loop."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
from typing import Any, Mapping


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


class EvidenceLevel(str, Enum):
    E0 = "E0"  # model hypothesis
    E1 = "E1"  # static declaration
    E2 = "E2"  # single observation
    E3 = "E3"  # repeated observation
    E4 = "E4"  # user or independent confirmation
    E5 = "E5"  # isolated customer journey closure


class FactStatus(str, Enum):
    OBSERVED = "observed"
    DECLARED = "declared"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    UNKNOWN = "unknown"
    SUPERSEDED = "superseded"


class RunStatus(str, Enum):
    PLANNED = "planned"
    RUNNING = "running"
    PASS = "pass"
    FAIL = "fail"
    BLOCKED = "blocked"
    INCONCLUSIVE = "inconclusive"
    NOT_RUN = "not_run"
    NEEDS_HUMAN = "needs_human"


class StepStatus(str, Enum):
    PLANNED = "planned"
    READY = "ready"
    RUNNING = "running"
    OBSERVED = "observed"
    VALIDATED = "validated"
    SETTLED = "settled"
    FAILED = "failed"
    BLOCKED = "blocked"
    UNKNOWN = "unknown"
    NEEDS_HUMAN = "needs_human"


class FindingKind(str, Enum):
    CONTRACT_VIOLATION = "contract_violation"
    OUTCOME_FAILURE = "outcome_failure"
    BEHAVIOR_BYPASS = "behavior_bypass"
    HUMAN_FRICTION = "human_friction"
    SECURITY_RISK = "security_risk"
    ADAPTER_ERROR = "adapter_error"


class Severity(str, Enum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True)
class EvidenceRef:
    evidence_id: str
    source: str
    level: EvidenceLevel
    summary: str
    payload_digest: str
    created_at: str = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        if not self.evidence_id.strip() or not self.source.strip():
            raise ValueError("evidence identity and source are required")
        if not self.summary.strip():
            raise ValueError("evidence summary is required")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self) | {"level": self.level.value}


@dataclass(frozen=True)
class ContractHypothesis:
    path: str
    value: Any
    status: FactStatus
    level: EvidenceLevel
    evidence_ids: tuple[str, ...] = ()
    revision: int = 1
    created_at: str = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        if not self.path.strip() or self.revision < 1:
            raise ValueError("hypothesis path and positive revision are required")

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        data["level"] = self.level.value
        data["evidence_ids"] = list(self.evidence_ids)
        return data

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ContractHypothesis":
        return cls(
            path=str(data["path"]),
            value=data.get("value"),
            status=FactStatus(str(data["status"])),
            level=EvidenceLevel(str(data["level"])),
            evidence_ids=tuple(str(item) for item in data.get("evidence_ids", ())),
            revision=int(data.get("revision", 1)),
            created_at=str(data.get("created_at") or utc_now()),
        )


@dataclass(frozen=True)
class AgentContractProfile:
    agent_id: str
    adapter_id: str
    purpose: str = ""
    revision: int = 1
    input_schema: dict[str, Any] | None = None
    output_schema: dict[str, Any] | None = None
    error_schema: dict[str, Any] | None = None
    tools: tuple[dict[str, Any], ...] = ()
    hypotheses: tuple[ContractHypothesis, ...] = ()
    evidence_ids: tuple[str, ...] = ()
    created_at: str = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        if not self.agent_id.strip() or not self.adapter_id.strip():
            raise ValueError("agent and adapter identity are required")
        if self.revision < 1:
            raise ValueError("profile revision must be positive")

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["hypotheses"] = [item.to_dict() for item in self.hypotheses]
        data["evidence_ids"] = list(self.evidence_ids)
        data["tools"] = [dict(item) for item in self.tools]
        return data

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "AgentContractProfile":
        return cls(
            agent_id=str(data["agent_id"]),
            adapter_id=str(data["adapter_id"]),
            purpose=str(data.get("purpose") or ""),
            revision=int(data.get("revision", 1)),
            input_schema=dict(data["input_schema"]) if isinstance(data.get("input_schema"), dict) else None,
            output_schema=dict(data["output_schema"]) if isinstance(data.get("output_schema"), dict) else None,
            error_schema=dict(data["error_schema"]) if isinstance(data.get("error_schema"), dict) else None,
            tools=tuple(dict(item) for item in data.get("tools", ()) if isinstance(item, Mapping)),
            hypotheses=tuple(
                ContractHypothesis.from_dict(item)
                for item in data.get("hypotheses", ())
                if isinstance(item, Mapping)
            ),
            evidence_ids=tuple(str(item) for item in data.get("evidence_ids", ())),
            created_at=str(data.get("created_at") or utc_now()),
        )

    def with_hypothesis(self, hypothesis: ContractHypothesis) -> "AgentContractProfile":
        retained = tuple(
            item
            for item in self.hypotheses
            if item.path != hypothesis.path or item.status is FactStatus.SUPERSEDED
        )
        return AgentContractProfile(
            agent_id=self.agent_id,
            adapter_id=self.adapter_id,
            purpose=self.purpose,
            revision=self.revision + 1,
            input_schema=self.input_schema,
            output_schema=self.output_schema,
            error_schema=self.error_schema,
            tools=self.tools,
            hypotheses=retained + (hypothesis,),
            evidence_ids=tuple(dict.fromkeys(self.evidence_ids + hypothesis.evidence_ids)),
        )


@dataclass(frozen=True)
class JourneyStep:
    step_id: str
    kind: str
    payload: Any = None
    assertions: tuple[dict[str, Any], ...] = ()
    description: str = ""

    def __post_init__(self) -> None:
        if not self.step_id.strip() or self.kind not in {"user_input", "expect", "observe", "reset"}:
            raise ValueError("invalid journey step")

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["assertions"] = [dict(item) for item in self.assertions]
        return data


@dataclass(frozen=True)
class CustomerJourney:
    scenario_id: str
    goal: str
    steps: tuple[JourneyStep, ...]
    actor: dict[str, Any] = field(default_factory=dict)
    preconditions: tuple[str, ...] = ()
    side_effect_policy: str = "read_only"
    source: str = "customer_trace"
    revision: int = 1
    evidence_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.scenario_id.strip() or not self.goal.strip() or not self.steps:
            raise ValueError("journey identity, goal and steps are required")
        if self.side_effect_policy not in {"read_only", "sandbox_write", "human_approved_write"}:
            raise ValueError("unsupported side effect policy")

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["steps"] = [step.to_dict() for step in self.steps]
        data["preconditions"] = list(self.preconditions)
        data["evidence_ids"] = list(self.evidence_ids)
        return data


@dataclass(frozen=True)
class RawObservation:
    output: Any = None
    status: str = "ok"
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    observed_at: str = field(default_factory=utc_now)

    @property
    def is_unknown(self) -> bool:
        return self.status in {"unknown", "timeout", "side_effect_unknown"}

    @property
    def is_blocked(self) -> bool:
        return self.status in {"blocked", "approval_required"}

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class InteractionEvent:
    event_id: str
    run_id: str
    step_id: str
    direction: str
    payload: Any
    payload_digest: str
    created_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class StepResult:
    step_id: str
    status: StepStatus
    observation: RawObservation | None = None
    assertion_errors: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        data["observation"] = self.observation.to_dict() if self.observation else None
        data["assertion_errors"] = list(self.assertion_errors)
        data["evidence_ids"] = list(self.evidence_ids)
        return data


@dataclass(frozen=True)
class Finding:
    finding_id: str
    run_id: str
    kind: FindingKind
    severity: Severity
    title: str
    detail: str
    step_id: str | None = None
    evidence_ids: tuple[str, ...] = ()
    created_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["kind"] = self.kind.value
        data["severity"] = self.severity.value
        data["evidence_ids"] = list(self.evidence_ids)
        return data


@dataclass(frozen=True)
class TestRun:
    run_id: str
    scenario_id: str
    agent_id: str
    profile_revision: int
    status: RunStatus
    step_results: tuple[StepResult, ...] = ()
    finding_ids: tuple[str, ...] = ()
    started_at: str = field(default_factory=utc_now)
    finished_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        data["step_results"] = [step.to_dict() for step in self.step_results]
        data["finding_ids"] = list(self.finding_ids)
        return data


@dataclass(frozen=True)
class Correction:
    correction_id: str
    target: str
    old_hypothesis: Any
    corrected_fact: Any
    reason: str
    evidence_ids: tuple[str, ...]
    regression_scenarios: tuple[str, ...] = ()
    created_at: str = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        if not self.correction_id.strip() or not self.target.strip() or not self.reason.strip():
            raise ValueError("correction identity, target and reason are required")

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["evidence_ids"] = list(self.evidence_ids)
        data["regression_scenarios"] = list(self.regression_scenarios)
        return data


@dataclass(frozen=True)
class EvolutionProposal:
    proposal_id: str
    kind: str
    base_revision: int
    proposed_change: dict[str, Any]
    evidence_ids: tuple[str, ...]
    risk: str = "normal"
    status: str = "proposed"
    created_at: str = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        if self.kind not in {"contract", "scenario", "evaluator", "workflow", "team"}:
            raise ValueError("unsupported evolution proposal kind")
        if self.risk not in {"low", "normal", "high", "critical"}:
            raise ValueError("unsupported proposal risk")

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["evidence_ids"] = list(self.evidence_ids)
        return data


@dataclass(frozen=True)
class RegressionPlan:
    plan_id: str
    correction_id: str
    selected_scenario_ids: tuple[str, ...]
    affected_paths: tuple[str, ...]
    reasons: tuple[str, ...]
    status: str = "planned"
    created_at: str = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        if not self.plan_id.strip() or not self.correction_id.strip():
            raise ValueError("regression plan identity is required")
        if not self.selected_scenario_ids:
            raise ValueError("regression plan must select at least one scenario")
        if self.status not in {"planned", "running", "completed", "blocked"}:
            raise ValueError("unsupported regression plan status")

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["selected_scenario_ids"] = list(self.selected_scenario_ids)
        data["affected_paths"] = list(self.affected_paths)
        data["reasons"] = list(self.reasons)
        return data


@dataclass(frozen=True)
class ProposalDecision:
    decision_id: str
    proposal_id: str
    decision: str
    decided_by: str
    human_approved: bool
    reason: str
    created_at: str = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        if self.decision not in {"approved", "rejected", "shadow"}:
            raise ValueError("unsupported proposal decision")
        if not self.decided_by.strip() or not self.reason.strip():
            raise ValueError("proposal decision actor and reason are required")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
