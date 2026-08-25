"""Human-gated proposal records and deterministic canary settlement.

This module never mutates an active tester registry. It owns only tester-domain
proposals, operator intent and replayable comparison metrics.
"""
from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass

from .ledger import EvidenceLedger
from .models import EvolutionProposal, ProposalDecision, RunStatus, TestRun


@dataclass(frozen=True)
class EvolutionApproval:
    """Explicit control-plane intent for one supervised evolution candidate."""

    approved: bool
    decided_by: str
    reason: str
    human_approved: bool = False
    minimum_quality_score: float = 1.0

    def __post_init__(self) -> None:
        if not self.decided_by.strip() or not self.reason.strip():
            raise ValueError("evolution approval actor and reason are required")
        if not 0 <= self.minimum_quality_score <= 1:
            raise ValueError("minimum quality score must be between 0 and 1")
        if self.approved and not self.human_approved:
            raise PermissionError(
                "supervised evolution application requires explicit human approval"
            )

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class EvolutionCanaryMetrics:
    """Comparable, deterministic metrics for one baseline/canary pair."""

    baseline_run_id: str
    canary_run_id: str
    baseline_status: str
    canary_status: str
    baseline_finding_count: int
    canary_finding_count: int
    ledger_integrity_ok: bool
    quality_score: float
    threshold: float
    verdict: str

    def __post_init__(self) -> None:
        if self.verdict not in {"beneficial", "neutral", "harmful"}:
            raise ValueError("unsupported evolution canary verdict")
        if not 0 <= self.quality_score <= 1 or not 0 <= self.threshold <= 1:
            raise ValueError("canary scores must be between 0 and 1")

    @property
    def accepted(self) -> bool:
        return self.verdict != "harmful" and self.quality_score >= self.threshold

    def to_dict(self) -> dict[str, object]:
        return asdict(self) | {"accepted": self.accepted}


def evaluate_evolution_canary(
    baseline: TestRun,
    canary: TestRun,
    *,
    ledger_integrity_ok: bool,
    minimum_quality_score: float,
) -> EvolutionCanaryMetrics:
    """Settle one customer-like canary without model self-grading.

    A candidate is harmful when the healthy baseline is lost, evidence fails
    integrity, or the canary adds findings.  Equal evidence-backed PASS results
    are neutral and may be accepted only because a human approved the revision.
    """
    baseline_healthy = baseline.status is RunStatus.PASS
    canary_healthy = canary.status is RunStatus.PASS
    finding_delta = len(canary.finding_ids) - len(baseline.finding_ids)
    quality_score = 1.0 if canary_healthy and ledger_integrity_ok else 0.0
    if not baseline_healthy or not canary_healthy or not ledger_integrity_ok:
        verdict = "harmful"
    elif finding_delta > 0:
        verdict = "harmful"
    elif finding_delta < 0:
        verdict = "beneficial"
    else:
        verdict = "neutral"
    return EvolutionCanaryMetrics(
        baseline_run_id=baseline.run_id,
        canary_run_id=canary.run_id,
        baseline_status=baseline.status.value,
        canary_status=canary.status.value,
        baseline_finding_count=len(baseline.finding_ids),
        canary_finding_count=len(canary.finding_ids),
        ledger_integrity_ok=ledger_integrity_ok,
        quality_score=quality_score,
        threshold=minimum_quality_score,
        verdict=verdict,
    )


class EvolutionGovernor:
    """Persist proposals and decisions without applying registry mutations."""

    def __init__(self, ledger: EvidenceLedger) -> None:
        self.ledger = ledger

    def submit(self, proposal: EvolutionProposal) -> None:
        self.ledger.append(proposal.proposal_id, "evolution.proposal", proposal.proposal_id, proposal.to_dict())

    def decide(
        self,
        proposal: EvolutionProposal,
        *,
        decision: str,
        decided_by: str,
        reason: str,
        human_approved: bool = False,
    ) -> ProposalDecision:
        if decision == "approved" and proposal.kind in {"contract", "evaluator"} and not human_approved:
            raise PermissionError("contract and evaluator evolution requires explicit human approval")
        record = ProposalDecision(
            decision_id=f"decision_{uuid.uuid4().hex}",
            proposal_id=proposal.proposal_id,
            decision=decision,
            decided_by=decided_by,
            human_approved=human_approved,
            reason=reason,
        )
        self.ledger.append(record.decision_id, "evolution.decision", proposal.proposal_id, record.to_dict())
        return record
