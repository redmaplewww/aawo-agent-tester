"""Optional AAWO 0.6.0.dev41 runtime integration.

The deterministic tester remains the authority for customer-journey execution
and test settlement.  AAWO owns capability registration, the runtime Team Tree,
the revisable workflow, scoped evidence, handoffs, checkpoints and lifecycle.
"""
from __future__ import annotations

import importlib
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .aawo_compat import (
    TesterBlueprint,
    default_test_blueprints,
    register_departments_with_aawo,
)
from .adapters import UnderTestAdapter
from .evolution import (
    AAWOEvolutionResult,
    EvolutionApproval,
    EvolutionGovernor,
    evaluate_evolution_canary,
)
from .ledger import EvidenceLedger
from .models import (
    AgentContractProfile,
    CustomerJourney,
    EvolutionProposal,
    FindingKind,
    RunStatus,
    TestRun,
    digest,
)
from .reasoning import ReasoningProvider, ReasoningProviderError
from .runner import CustomerSimulationRunner, side_effect_allowed

SUPPORTED_AAWO_VERSION = "0.6.0.dev41"
_WORKFLOW_NODE_ID = "execute_customer_journey_test"
_EXECUTED_ROLE_IDS = (
    "environment-operator",
    "contract-miner",
    "customer-simulator",
    "protocol-verifier",
    "outcome-reviewer",
    "ux-friction-reviewer",
    "evidence-auditor",
)


class AAWORuntimeUnavailable(RuntimeError):
    """Raised when the optional AAWO public runtime cannot be used safely."""


def require_aawo_runtime() -> Any:
    """Load and verify the intentionally frozen AAWO dev41 public API."""
    try:
        aawo = importlib.import_module("aawo")
    except ImportError as exc:
        raise AAWORuntimeUnavailable(
            "AAWO runtime is optional; install the supplied aawo==0.6.0.dev41 wheel"
        ) from exc
    version = str(getattr(aawo, "__version__", ""))
    if version != SUPPORTED_AAWO_VERSION:
        raise AAWORuntimeUnavailable(
            f"AAWO {SUPPORTED_AAWO_VERSION} is required, found {version or 'unknown'}"
        )
    manifest = aawo.public_api_manifest()
    required = {
        "AgentServices",
        "AgentResult",
        "ApprovalRecord",
        "DepartmentPool",
        "EvidenceRef",
        "ProductionControlPlane",
        "PermissionDenied",
        "RecruitmentRequest",
        "ReleaseMode",
        "SQLiteDepartmentStore",
        "TeamExecutionSpec",
        "TeamExecutor",
        "TeamRoleSpec",
        "TeamIntegrityError",
        "WorkflowSeed",
        "WorkflowRevisionProposal",
        "WorkforceOrchestrator",
        "redact",
    }
    missing = required - set(manifest["exports"])
    if missing:
        raise AAWORuntimeUnavailable(
            f"AAWO public API is missing required exports: {sorted(missing)}"
        )
    return aawo


def journey_to_aawo_workflow_data(journey: CustomerJourney) -> dict[str, Any]:
    """Project one CustomerJourney into an executable AAWO coordination node.

    The customer's individual steps remain the tester's domain contract.  The
    AAWO workflow owns the accountable operation that executes and audits that
    immutable journey; this avoids turning the Team Tree into a business flow.
    """
    risk = {
        "read_only": "low",
        "sandbox_write": "normal",
        "human_approved_write": "high",
    }[journey.side_effect_policy]
    origin = "ai" if "model" in journey.source.lower() else "human"
    return {
        "representation": "dependency",
        "definition": {
            "work_nodes": [{
                "node_id": _WORKFLOW_NODE_ID,
                "objective": (
                    f"Execute and independently audit CustomerJourney "
                    f"{journey.scenario_id}: {journey.goal}"
                ),
                "required_capabilities": ["test-orchestration"],
                "acceptance_criteria": [
                    "Preserve the exact PASS/FAIL/BLOCKED/INCONCLUSIVE result.",
                    "Bind the conclusion to scoped immutable evidence.",
                    "Do not exceed the declared side-effect policy.",
                ],
                "risk_level": risk,
                "tags": ["agent-test", "test-director"],
                "max_attempts": 1,
                "failure_policy": "stop",
                "cancellation_policy": "review",
            }],
            "customer_journey": {
                "scenario_id": journey.scenario_id,
                "revision": journey.revision,
                "source": journey.source,
                "step_ids": [step.step_id for step in journey.steps],
                "side_effect_policy": journey.side_effect_policy,
                "contract_digest": digest(journey.to_dict()),
            },
        },
        "initialized_by": "aawo-agent-tester-host",
        "origin": origin,
        "adaptation_mode": "supervised",
        "constraints": [
            "customer_journey_is_immutable_for_one_run",
            "failed_blocked_and_unknown_are_never_promoted_to_pass",
            "workflow_revision_requires_evidence_and_governance",
        ],
        "activation_hints": {"max_concurrency": 1},
    }


def aawo_test_team_spec_data() -> dict[str, Any]:
    """Return the identity-free AAWO test-team composition contract."""
    return {
        "composition_id": "aawo-agent-customer-test/v1",
        "description": (
            "Cross-department, evidence-first team that executes one immutable "
            "customer journey and reports upward through independent reviews."
        ),
        "max_parallelism": 2,
        "roles": [
            {
                "role_key": "environment-operator",
                "objective": "Preflight fixtures, adapter identity and side-effect containment.",
                "required_capabilities": ["sandbox-operation"],
                "department_id": "agent_test_execution",
                "blueprint_id": "environment-operator",
                "parent_role_key": "customer-simulator",
                "risk_level": "high",
            },
            {
                "role_key": "contract-miner",
                "objective": "Freeze the declared profile revision and its evidence-bound contract digest.",
                "required_capabilities": ["contract-inference"],
                "department_id": "agent_test_understanding",
                "blueprint_id": "contract-miner",
                "parent_role_key": "customer-simulator",
            },
            {
                "role_key": "customer-simulator",
                "objective": "Execute the immutable customer journey through the deterministic adapter boundary.",
                "required_capabilities": ["customer-journey"],
                "department_id": "agent_test_execution",
                "blueprint_id": "customer-simulator",
                "parent_role_key": "protocol-verifier",
                "depends_on": ["environment-operator", "contract-miner"],
                "risk_level": "high",
            },
            {
                "role_key": "protocol-verifier",
                "objective": "Review contract and adapter findings without changing the observed run.",
                "required_capabilities": ["contract-validation"],
                "department_id": "agent_test_review",
                "blueprint_id": "protocol-verifier",
                "parent_role_key": "outcome-reviewer",
                "depends_on": ["customer-simulator"],
            },
            {
                "role_key": "outcome-reviewer",
                "objective": "Settle whether the customer goal actually completed from the recorded run status.",
                "required_capabilities": ["domain-outcome-review"],
                "department_id": "agent_test_review",
                "blueprint_id": "outcome-reviewer",
                "parent_role_key": "ux-friction-reviewer",
                "depends_on": ["protocol-verifier"],
            },
            {
                "role_key": "ux-friction-reviewer",
                "objective": "Report evidence-bound customer friction independently from protocol correctness.",
                "required_capabilities": ["human-factors"],
                "department_id": "agent_test_review",
                "blueprint_id": "ux-friction-reviewer",
                "parent_role_key": "evidence-auditor",
                "depends_on": ["outcome-reviewer"],
            },
            {
                "role_key": "evidence-auditor",
                "objective": "Verify ledger hashes, terminal settlement and conclusion authority.",
                "required_capabilities": ["evidence-audit"],
                "department_id": "agent_test_review",
                "blueprint_id": "evidence-auditor",
                "depends_on": ["ux-friction-reviewer"],
                "risk_level": "high",
            },
        ],
    }


@dataclass(frozen=True)
class AAWOTestTeamResult:
    """Detached result returned after the AAWO team is explicitly released."""

    test_run: TestRun
    team_id: str
    workflow_id: str
    workflow_status: dict[str, Any]
    team_snapshot: dict[str, Any]
    team_result: dict[str, Any]
    evidence_refs: tuple[dict[str, Any], ...]
    release_order: tuple[str, ...]
    aawo_store_path: str
    evolution: AAWOEvolutionResult | None = None
    llm_proposal: EvolutionProposal | None = None
    llm_proposal_error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "aawo.agent_test_runtime_result/v1",
            "test_run": self.test_run.to_dict(),
            "team_id": self.team_id,
            "workflow_id": self.workflow_id,
            "workflow_status": self.workflow_status,
            "team_snapshot": self.team_snapshot,
            "team_result": self.team_result,
            "evidence_refs": list(self.evidence_refs),
            "release_order": list(self.release_order),
            "aawo_store_path": self.aawo_store_path,
            "evolution": self.evolution.to_dict() if self.evolution is not None else None,
            "llm_proposal": self.llm_proposal.to_dict() if self.llm_proposal is not None else None,
            "llm_proposal_error": self.llm_proposal_error,
        }


@dataclass
class _ExecutionState:
    ledger: EvidenceLedger
    profile: AgentContractProfile
    journey: CustomerJourney
    adapter: UnderTestAdapter
    runner: CustomerSimulationRunner
    test_run: TestRun | None = None
    evidence_refs: list[dict[str, Any]] = field(default_factory=list)

    def require_run(self) -> TestRun:
        if self.test_run is None:
            raise RuntimeError("customer journey has not produced a settled TestRun")
        return self.test_run

    def record_evidence(
        self,
        services: Any,
        content: dict[str, Any],
        *,
        kind: str,
    ) -> dict[str, Any]:
        reference = services.record_evidence(content, kind=kind).snapshot()
        self.evidence_refs.append(reference)
        return reference


class _TestRoleExecutor:
    def __init__(self, role_id: str, state: _ExecutionState, aawo: Any) -> None:
        self.role_id = role_id
        self.state = state
        self.aawo = aawo

    async def run(self, context: Any, services: Any) -> Any:
        handler = getattr(self, f"_run_{self.role_id.replace('-', '_')}")
        return await handler(context, services)

    async def _run_environment_operator(self, _context: Any, services: Any) -> Any:
        description = self.state.adapter.describe()
        allowed = side_effect_allowed(
            self.state.journey.side_effect_policy,
            description.side_effect_policy,
        )
        evidence = self.state.record_evidence(services, {
            "schema": "aawo.agent_test_environment_preflight/v1",
            "scenario_id": self.state.journey.scenario_id,
            "adapter_id": description.adapter_id,
            "channel": description.channel,
            "journey_side_effect_policy": self.state.journey.side_effect_policy,
            "adapter_side_effect_policy": description.side_effect_policy,
            "allowed": allowed,
        }, kind="environment_preflight")
        return self.aawo.AgentResult(
            output={
                "schema": "aawo.agent_test_environment_result/v1",
                "allowed": allowed,
                "adapter_id": description.adapter_id,
            },
            summary="Side-effect boundary is contained." if allowed else "Journey will settle BLOCKED before adapter invocation.",
            evidence=(evidence,),
        )

    async def _run_contract_miner(self, _context: Any, services: Any) -> Any:
        profile_digest = digest(self.state.profile.to_dict())
        evidence = self.state.record_evidence(services, {
            "schema": "aawo.agent_test_contract_snapshot/v1",
            "agent_id": self.state.profile.agent_id,
            "adapter_id": self.state.profile.adapter_id,
            "profile_revision": self.state.profile.revision,
            "profile_digest": profile_digest,
            "declared_input_schema": self.state.profile.input_schema is not None,
            "declared_output_schema": self.state.profile.output_schema is not None,
            "source_evidence_ids": list(self.state.profile.evidence_ids),
        }, kind="contract_snapshot")
        return self.aawo.AgentResult(
            output={
                "schema": "aawo.agent_test_contract_result/v1",
                "profile_revision": self.state.profile.revision,
                "profile_digest": profile_digest,
            },
            summary="Profile revision was frozen before test execution.",
            evidence=(evidence,),
        )

    async def _run_customer_simulator(self, _context: Any, services: Any) -> Any:
        if self.state.test_run is None:
            self.state.test_run = await self.state.runner.run(
                self.state.journey,
                self.state.profile,
                self.state.adapter,
            )
        run = self.state.require_run()
        evidence = self.state.record_evidence(services, {
            "schema": "aawo.agent_test_run_settlement/v1",
            "run_id": run.run_id,
            "scenario_id": run.scenario_id,
            "agent_id": run.agent_id,
            "profile_revision": run.profile_revision,
            "status": run.status.value,
            "finding_ids": list(run.finding_ids),
            "run_digest": digest(run.to_dict()),
            "ledger_record_count": len(self.state.ledger.records(aggregate_id=run.run_id)),
        }, kind="customer_journey_settlement")
        return self.aawo.AgentResult(
            output={
                "schema": "aawo.agent_test_customer_run_result/v1",
                "run_id": run.run_id,
                "status": run.status.value,
                "finding_ids": list(run.finding_ids),
            },
            summary=f"Customer journey settled as {run.status.value}; the status was not rewritten.",
            evidence=(evidence,),
        )

    async def _run_protocol_verifier(self, _context: Any, services: Any) -> Any:
        run = self.state.require_run()
        findings = self._finding_payloads(run)
        protocol_findings = [
            item for item in findings
            if item.get("kind") in {
                FindingKind.CONTRACT_VIOLATION.value,
                FindingKind.ADAPTER_ERROR.value,
                FindingKind.BEHAVIOR_BYPASS.value,
            }
        ]
        evidence = self.state.record_evidence(services, {
            "schema": "aawo.agent_test_protocol_review/v1",
            "run_id": run.run_id,
            "protocol_finding_ids": [item.get("finding_id") for item in protocol_findings],
            "protocol_finding_count": len(protocol_findings),
        }, kind="protocol_review")
        return self.aawo.AgentResult(
            output={
                "schema": "aawo.agent_test_protocol_result/v1",
                "run_id": run.run_id,
                "finding_count": len(protocol_findings),
                "validated": not protocol_findings,
            },
            summary=f"Protocol review retained {len(protocol_findings)} relevant findings.",
            evidence=(evidence,),
        )

    async def _run_outcome_reviewer(self, _context: Any, services: Any) -> Any:
        run = self.state.require_run()
        completed = run.status is RunStatus.PASS
        evidence = self.state.record_evidence(services, {
            "schema": "aawo.agent_test_outcome_review/v1",
            "run_id": run.run_id,
            "settled_status": run.status.value,
            "customer_goal_completed": completed,
            "finding_ids": list(run.finding_ids),
        }, kind="outcome_review")
        return self.aawo.AgentResult(
            output={
                "schema": "aawo.agent_test_outcome_result/v1",
                "run_id": run.run_id,
                "settled_status": run.status.value,
                "customer_goal_completed": completed,
            },
            summary=(
                "Customer goal completed under the confirmed journey."
                if completed
                else f"Customer goal did not complete; exact status is {run.status.value}."
            ),
            evidence=(evidence,),
        )

    async def _run_ux_friction_reviewer(self, _context: Any, services: Any) -> Any:
        run = self.state.require_run()
        friction = [
            item for item in self._finding_payloads(run)
            if item.get("kind") == FindingKind.HUMAN_FRICTION.value
        ]
        evidence = self.state.record_evidence(services, {
            "schema": "aawo.agent_test_friction_review/v1",
            "run_id": run.run_id,
            "friction_finding_ids": [item.get("finding_id") for item in friction],
            "friction_finding_count": len(friction),
        }, kind="human_friction_review")
        return self.aawo.AgentResult(
            output={
                "schema": "aawo.agent_test_friction_result/v1",
                "run_id": run.run_id,
                "finding_count": len(friction),
            },
            summary=f"Human-friction review retained {len(friction)} evidence-bound findings.",
            evidence=(evidence,),
        )

    async def _run_evidence_auditor(self, _context: Any, services: Any) -> Any:
        run = self.state.require_run()
        errors = list(self.state.ledger.verify_integrity(aggregate_id=run.run_id))
        records = self.state.ledger.records(aggregate_id=run.run_id)
        record_types = {item["record_type"] for item in records}
        if "test_run.created" not in record_types:
            errors.append("missing test_run.created record")
        final_records = [
            item for item in records
            if item["record_type"] == "test_run.status"
            and item["payload"].get("status") == run.status.value
        ]
        if not final_records:
            errors.append("missing exact terminal test_run.status record")
        if errors:
            raise RuntimeError("evidence audit failed: " + "; ".join(errors))
        evidence = self.state.record_evidence(services, {
            "schema": "aawo.agent_test_evidence_audit/v1",
            "run_id": run.run_id,
            "record_count": len(records),
            "terminal_status": run.status.value,
            "integrity_ok": True,
            "ledger_scope_digest": digest([
                {"record_id": item["record_id"], "payload_hash": item["payload_hash"]}
                for item in records
            ]),
        }, kind="evidence_audit")
        return self.aawo.AgentResult(
            output={
                "schema": "aawo.agent_test_evidence_result/v1",
                "run_id": run.run_id,
                "record_count": len(records),
                "integrity_ok": True,
            },
            summary="Evidence hashes and the exact terminal settlement were verified.",
            evidence=(evidence,),
        )

    def _finding_payloads(self, run: TestRun) -> list[dict[str, Any]]:
        payloads: list[dict[str, Any]] = []
        for finding_id in run.finding_ids:
            record = self.state.ledger.get(finding_id)
            if record is not None and isinstance(record.get("payload"), dict):
                payloads.append(dict(record["payload"]))
        return payloads


class _TestTeamAggregator:
    def __init__(self, state: _ExecutionState, aawo: Any) -> None:
        self.state = state
        self.aawo = aawo

    def aggregate(self, context: Any, spec: Any, members: tuple[Any, ...]) -> Any:
        run = self.state.require_run()
        return self.aawo.AgentResult(
            output={
                "schema": "aawo.agent_test_team_result/v1",
                "composition_id": spec.composition_id,
                "spec_digest": spec.digest,
                "leader_agent_id": context.lease.agent_id,
                "run_id": run.run_id,
                "status": run.status.value,
                "scenario_id": run.scenario_id,
                "profile_revision": run.profile_revision,
                "finding_ids": list(run.finding_ids),
                "members": [member.snapshot() for member in members],
            },
            summary=f"AAWO test team preserved customer-journey status {run.status.value}.",
            evidence=tuple(
                evidence
                for member in members
                for evidence in member.result.evidence
            ),
        )


def _build_team_spec(
    aawo: Any,
    *,
    composition_id: str | None = None,
) -> Any:
    data = aawo_test_team_spec_data()
    roles = tuple(
        aawo.TeamRoleSpec(
            role_key=item["role_key"],
            objective=item["objective"],
            required_capabilities=frozenset(item["required_capabilities"]),
            department_id=item["department_id"],
            blueprint_id=item["blueprint_id"],
            parent_role_key=item.get("parent_role_key"),
            depends_on=tuple(item.get("depends_on", ())),
            risk_level=item.get("risk_level", "normal"),
            tags=frozenset({"agent-test", item["role_key"]}),
        )
        for item in data["roles"]
    )
    return aawo.TeamExecutionSpec(
        composition_id or data["composition_id"],
        roles,
        max_parallelism=data["max_parallelism"],
        description=data["description"],
    )


class _RevisionAwareTeamExecutor:
    """Delegate each workflow revision to an isolated AAWO composition.

    AAWO intentionally uses stable composition work-item keys for retry/reuse.
    A semantic workflow canary must therefore receive a new composition identity
    or it would replay the accepted baseline instead of exercising the target.
    """

    def __init__(self, state: _ExecutionState, aawo: Any) -> None:
        self.state = state
        self.aawo = aawo

    async def run(self, context: Any, services: Any) -> Any:
        binding = dict(context.assignment_context.get("workflow_node_binding", {}))
        revision = int(binding.get("workflow_revision") or 1)
        base_id = str(aawo_test_team_spec_data()["composition_id"])
        composition_id = (
            base_id
            if revision == 1
            else f"{base_id}/workflow-revision/{revision}"
        )
        executor = self.aawo.TeamExecutor(
            _build_team_spec(self.aawo, composition_id=composition_id),
            _TestTeamAggregator(self.state, self.aawo),
        )
        return await executor.run(context, services)


def _evolution_result(
    proposal: EvolutionProposal,
    *,
    status: str,
    reason: str,
    workflow: Any,
    aawo_proposal_id: str | None = None,
    approval_id: str | None = None,
    control_ledger_id: str | None = None,
    base_revision: int | None = None,
    canary_run: TestRun | None = None,
    metrics: Any | None = None,
    rolled_back: bool = False,
) -> AAWOEvolutionResult:
    return AAWOEvolutionResult(
        proposal_id=proposal.proposal_id,
        status=status,
        reason=reason,
        aawo_proposal_id=aawo_proposal_id,
        approval_id=approval_id,
        control_ledger_id=control_ledger_id,
        base_workflow_revision=base_revision or workflow.revision,
        final_workflow_revision=workflow.revision,
        canary_run=canary_run,
        metrics=metrics,
        rolled_back=rolled_back,
    )


def _record_evolution_control_event(
    control: Any,
    *,
    team_id: str,
    memory_scope: str,
    operation: str,
    proposal: EvolutionProposal,
    payload: dict[str, Any],
    status: str,
    owner_id: str,
    owner_epoch: int,
) -> str:
    return control.record_ledger(
        team_id,
        operation,
        {
            "schema": "aawo.agent_test_evolution_control/v1",
            "proposal_id": proposal.proposal_id,
            "kind": proposal.kind,
            "base_revision": proposal.base_revision,
            "proposal_digest": digest(proposal.to_dict()),
            **payload,
        },
        memory_scope=memory_scope,
        status=status,
        owner_id=owner_id,
        owner_epoch=owner_epoch,
    )


def _build_llm_evidence_context(
    state: _ExecutionState,
    baseline_run: TestRun,
) -> tuple[dict[str, Any], ...]:
    """Expose only bounded evidence metadata to the external reasoning model."""
    records = state.ledger.records(aggregate_id=baseline_run.run_id)
    context: list[dict[str, Any]] = []
    for record in records:
        payload = record.get("payload")
        payload_keys = sorted(str(key) for key in payload) if isinstance(payload, dict) else []
        context.append(
            {
                "evidence_id": record["record_id"],
                "record_type": record["record_type"],
                "status": (
                    payload.get("status") or payload.get("run_status")
                    if isinstance(payload, dict)
                    else ""
                ),
                "payload_keys": payload_keys[:32],
            }
        )
    return tuple(context)


def _rollback_harmful_workflow(
    runtime: Any,
    *,
    team_id: str,
    base_revision: int,
    expected_revision: int,
    actor: str,
    reason: str,
) -> Any:
    try:
        return runtime.rollback_workflow(
            team_id,
            base_revision,
            rolled_back_by=actor,
            reason=reason,
            expected_revision=expected_revision,
        )
    except Exception as exc:
        raise RuntimeError(
            "evolution candidate was unsafe and AAWO rollback did not complete"
        ) from exc


async def _run_controlled_workflow_evolution(
    *,
    aawo: Any,
    runtime: Any,
    root: Any,
    optimizer: Any,
    state: _ExecutionState,
    baseline_run: TestRun,
    proposal: EvolutionProposal,
    approval: EvolutionApproval | None,
    memory_scope: str,
) -> AAWOEvolutionResult:
    """Apply one supervised AAWO workflow candidate through a real canary.

    Unsupported tester-domain mutations remain proposal-only.  This function
    cannot edit Profile, Journey, Evaluator or TestRun registries.
    """
    governor = EvolutionGovernor(state.ledger)
    governor.submit(proposal)
    control = aawo.ProductionControlPlane(runtime.pool.store)
    owner_id = runtime.runtime_id
    owner_epoch = runtime.pool.store.claim_team_owner(root.team_id, owner_id)
    runtime.pool.store.assert_team_owner(root.team_id, owner_id, owner_epoch)
    workflow = runtime.active_workflow(root.team_id)
    if workflow is None:
        raise RuntimeError("AAWO workflow is unavailable for controlled evolution")

    def reject_before_application(reason: str) -> AAWOEvolutionResult:
        governor.decide(
            proposal,
            decision="rejected",
            decided_by=(approval.decided_by if approval else "policy:fail-closed"),
            reason=reason,
            human_approved=bool(approval and approval.human_approved),
        )
        ledger_id = _record_evolution_control_event(
            control,
            team_id=root.team_id,
            memory_scope=memory_scope,
            operation="evolution.rejected",
            proposal=proposal,
            payload={"reason": reason, "workflow_revision": workflow.revision},
            status="rejected",
            owner_id=owner_id,
            owner_epoch=owner_epoch,
        )
        return _evolution_result(
            proposal,
            status="rejected",
            reason=reason,
            workflow=workflow,
            control_ledger_id=ledger_id,
        )

    if proposal.kind != "workflow":
        return reject_before_application(
            "only workflow evolution has an AAWO application path in this release; "
            "contract, scenario, evaluator and team proposals remain proposal-only"
        )
    missing_evidence = tuple(
        evidence_id
        for evidence_id in proposal.evidence_ids
        if state.ledger.get(evidence_id) is None
    )
    if not proposal.evidence_ids or missing_evidence:
        return reject_before_application(
            "workflow evolution requires locally verifiable proposal evidence"
        )
    if proposal.base_revision != workflow.revision:
        return reject_before_application(
            "workflow evolution proposal is stale against the active AAWO revision"
        )
    if baseline_run.status is not RunStatus.PASS:
        return reject_before_application(
            "a non-passing baseline cannot authorize a quality evolution canary"
        )

    evidence_refs = tuple(
        aawo.EvidenceRef.from_dict(item) for item in state.evidence_refs
    )
    services = aawo.AgentServices(runtime, optimizer)
    try:
        aawo_proposal = services.revise_workflow(
            reason=(
                "Evidence-backed tester workflow candidate "
                f"{proposal.proposal_id}"
            ),
            changes=dict(proposal.proposed_change),
            evidence_ids=proposal.evidence_ids,
            evidence_refs=evidence_refs,
        )
    except (ValueError, aawo.PermissionDenied, aawo.TeamIntegrityError):
        return reject_before_application(
            "AAWO rejected the proposed workflow changes before application"
        )
    if not isinstance(aawo_proposal, aawo.WorkflowRevisionProposal):
        return reject_before_application(
            "supervised evolution unexpectedly bypassed the pending proposal boundary"
        )

    approval_record = aawo.ApprovalRecord(
        team_id=root.team_id,
        action="apply_agent_test_workflow_revision",
        requested_by=optimizer.agent_id,
        reason=f"Review evolution proposal {proposal.proposal_id}",
        risk=proposal.risk,
        evidence_ids=tuple(item.record_id for item in evidence_refs),
    )
    control.request_approval(
        approval_record,
        memory_scope=memory_scope,
        owner_id=owner_id,
        owner_epoch=owner_epoch,
    )
    if approval is None or not approval.approved:
        actor = approval.decided_by if approval is not None else "policy:fail-closed"
        reason = (
            approval.reason
            if approval is not None
            else "no explicit human approval was supplied"
        )
        control.decide_approval(
            approval_record.approval_id,
            approved=False,
            decided_by=actor,
            reason=reason,
            owner_id=owner_id,
            owner_epoch=owner_epoch,
        )
        workflow = runtime.decide_workflow_revision(
            root.team_id,
            aawo_proposal.proposal_id,
            approve=False,
            decided_by=actor,
            decision_reason=reason,
        )
        governor.decide(
            proposal,
            decision="rejected",
            decided_by=actor,
            reason=reason,
            human_approved=bool(approval and approval.human_approved),
        )
        ledger_id = _record_evolution_control_event(
            control,
            team_id=root.team_id,
            memory_scope=memory_scope,
            operation="evolution.rejected",
            proposal=proposal,
            payload={
                "aawo_proposal_id": aawo_proposal.proposal_id,
                "approval_id": approval_record.approval_id,
                "workflow_revision": workflow.revision,
            },
            status="rejected",
            owner_id=owner_id,
            owner_epoch=owner_epoch,
        )
        return _evolution_result(
            proposal,
            status="rejected",
            reason=reason,
            workflow=workflow,
            aawo_proposal_id=aawo_proposal.proposal_id,
            approval_id=approval_record.approval_id,
            control_ledger_id=ledger_id,
        )

    control.decide_approval(
        approval_record.approval_id,
        approved=True,
        decided_by=approval.decided_by,
        reason=approval.reason,
        owner_id=owner_id,
        owner_epoch=owner_epoch,
    )
    control.require_approved(approval_record.approval_id)
    governor.decide(
        proposal,
        decision="shadow",
        decided_by=approval.decided_by,
        reason="Apply only to the supervised AAWO canary revision",
        human_approved=True,
    )
    base_revision = workflow.revision
    workflow = runtime.decide_workflow_revision(
        root.team_id,
        aawo_proposal.proposal_id,
        approve=True,
        decided_by=approval.decided_by,
        decision_reason=approval.reason,
    )
    applied_revision = workflow.revision
    execution_impact = dict(workflow.history[-1].get("execution_impact", {}))
    changed_nodes = set(execution_impact.get("changed_node_ids", ()))
    if _WORKFLOW_NODE_ID not in changed_nodes:
        workflow = _rollback_harmful_workflow(
            runtime,
            team_id=root.team_id,
            base_revision=base_revision,
            expected_revision=applied_revision,
            actor=approval.decided_by,
            reason="Candidate did not create a fresh customer-journey canary execution",
        )
        governor.decide(
            proposal,
            decision="rejected",
            decided_by=approval.decided_by,
            reason="Candidate changed no executable test semantics",
            human_approved=True,
        )
        ledger_id = _record_evolution_control_event(
            control,
            team_id=root.team_id,
            memory_scope=memory_scope,
            operation="evolution.frozen",
            proposal=proposal,
            payload={
                "aawo_proposal_id": aawo_proposal.proposal_id,
                "approval_id": approval_record.approval_id,
                "freeze_reason": "no_fresh_canary_execution",
                "rolled_back_to_revision": base_revision,
                "result_revision": workflow.revision,
            },
            status="frozen",
            owner_id=owner_id,
            owner_epoch=owner_epoch,
        )
        return _evolution_result(
            proposal,
            status="frozen",
            reason="Candidate changed no executable test semantics",
            workflow=workflow,
            aawo_proposal_id=aawo_proposal.proposal_id,
            approval_id=approval_record.approval_id,
            control_ledger_id=ledger_id,
            base_revision=base_revision,
            rolled_back=True,
        )

    state.test_run = None
    try:
        canary_leader = await runtime.hire_for_workflow_node(
            root,
            _WORKFLOW_NODE_ID,
        )
        await runtime.run(canary_leader)
        runtime.finalize_subtree_summary(
            root.team_id,
            canary_leader.agent_id,
            finalized_by=canary_leader.agent_id,
        )
        canary_run = state.require_run()
        integrity_ok = not state.ledger.verify_integrity(
            aggregate_id=canary_run.run_id
        )
        metrics = evaluate_evolution_canary(
            baseline_run,
            canary_run,
            ledger_integrity_ok=integrity_ok,
            minimum_quality_score=approval.minimum_quality_score,
        )
    except Exception as exc:  # noqa: BLE001 - canary failure must trigger fail-closed rollback
        state.test_run = baseline_run
        workflow = _rollback_harmful_workflow(
            runtime,
            team_id=root.team_id,
            base_revision=base_revision,
            expected_revision=applied_revision,
            actor=approval.decided_by,
            reason="Canary execution failed and the candidate must be frozen",
        )
        governor.decide(
            proposal,
            decision="rejected",
            decided_by=approval.decided_by,
            reason="Canary execution failed; candidate frozen",
            human_approved=True,
        )
        ledger_id = _record_evolution_control_event(
            control,
            team_id=root.team_id,
            memory_scope=memory_scope,
            operation="evolution.frozen",
            proposal=proposal,
            payload={
                "aawo_proposal_id": aawo_proposal.proposal_id,
                "approval_id": approval_record.approval_id,
                "freeze_reason": "canary_execution_failed",
                "error_type": type(exc).__name__,
                "error_detail": str(aawo.redact(str(exc)))[:300],
                "rolled_back_to_revision": base_revision,
                "result_revision": workflow.revision,
            },
            status="frozen",
            owner_id=owner_id,
            owner_epoch=owner_epoch,
        )
        return _evolution_result(
            proposal,
            status="frozen",
            reason="Canary execution failed; candidate frozen",
            workflow=workflow,
            aawo_proposal_id=aawo_proposal.proposal_id,
            approval_id=approval_record.approval_id,
            control_ledger_id=ledger_id,
            base_revision=base_revision,
            rolled_back=True,
        )

    metric_ref = services.record_evidence(
        {
            "schema": "aawo.agent_test_evolution_canary/v1",
            "proposal_id": proposal.proposal_id,
            "aawo_proposal_id": aawo_proposal.proposal_id,
            "metrics": metrics.to_dict(),
        },
        kind="evolution_canary",
    )
    state.evidence_refs.append(metric_ref.snapshot())
    services.record_runtime_metric(
        "agent_test_evolution_canary",
        {
            "quality_score": metrics.quality_score,
            "threshold": metrics.threshold,
            "baseline_findings": metrics.baseline_finding_count,
            "canary_findings": metrics.canary_finding_count,
            "accepted": 1 if metrics.accepted else 0,
        },
    )
    if not metrics.accepted:
        workflow = _rollback_harmful_workflow(
            runtime,
            team_id=root.team_id,
            base_revision=base_revision,
            expected_revision=applied_revision,
            actor=approval.decided_by,
            reason="Customer-like canary was harmful or below threshold",
        )
        governor.decide(
            proposal,
            decision="rejected",
            decided_by=approval.decided_by,
            reason="Customer-like canary was harmful or below threshold",
            human_approved=True,
        )
        ledger_id = _record_evolution_control_event(
            control,
            team_id=root.team_id,
            memory_scope=memory_scope,
            operation="evolution.frozen",
            proposal=proposal,
            payload={
                "aawo_proposal_id": aawo_proposal.proposal_id,
                "approval_id": approval_record.approval_id,
                "metric_evidence_id": metric_ref.record_id,
                "metrics": metrics.to_dict(),
                "rolled_back_to_revision": base_revision,
                "result_revision": workflow.revision,
            },
            status="frozen",
            owner_id=owner_id,
            owner_epoch=owner_epoch,
        )
        return _evolution_result(
            proposal,
            status="frozen",
            reason="Customer-like canary was harmful or below threshold",
            workflow=workflow,
            aawo_proposal_id=aawo_proposal.proposal_id,
            approval_id=approval_record.approval_id,
            control_ledger_id=ledger_id,
            base_revision=base_revision,
            canary_run=canary_run,
            metrics=metrics,
            rolled_back=True,
        )

    governor.decide(
        proposal,
        decision="approved",
        decided_by=approval.decided_by,
        reason="Customer-like canary met the approved quality threshold",
        human_approved=True,
    )
    ledger_id = _record_evolution_control_event(
        control,
        team_id=root.team_id,
        memory_scope=memory_scope,
        operation="evolution.promoted",
        proposal=proposal,
        payload={
            "aawo_proposal_id": aawo_proposal.proposal_id,
            "approval_id": approval_record.approval_id,
            "metric_evidence_id": metric_ref.record_id,
            "metrics": metrics.to_dict(),
            "active_workflow_revision": workflow.revision,
        },
        status="promoted",
        owner_id=owner_id,
        owner_epoch=owner_epoch,
    )
    return _evolution_result(
        proposal,
        status="promoted",
        reason="Customer-like canary met the approved quality threshold",
        workflow=workflow,
        aawo_proposal_id=aawo_proposal.proposal_id,
        approval_id=approval_record.approval_id,
        control_ledger_id=ledger_id,
        base_revision=base_revision,
        canary_run=canary_run,
        metrics=metrics,
    )


class _EvolutionOptimizerExecutor:
    """Registered execution boundary for the accountable Optimizer role."""

    def __init__(self, aawo: Any) -> None:
        self.aawo = aawo

    async def run(self, context: Any, _services: Any) -> Any:
        return self.aawo.AgentResult(
            output={
                "schema": "aawo.agent_test_evolution_optimizer/v1",
                "agent_id": context.lease.agent_id,
                "ready": True,
            },
            summary="Optimizer is ready to emit proposals; it has no apply authority.",
        )


class AAWOTestTeamRunner:
    """Run one deterministic customer test inside a real AAWO team and workflow."""

    def __init__(
        self,
        ledger: EvidenceLedger,
        *,
        aawo_store_path: str | Path = ":memory:",
    ) -> None:
        self.ledger = ledger
        self.aawo_store_path = str(aawo_store_path)

    async def run(
        self,
        journey: CustomerJourney,
        profile: AgentContractProfile,
        adapter: UnderTestAdapter,
        *,
        memory_scope: str | None = None,
        evolution_proposal: EvolutionProposal | None = None,
        evolution_approval: EvolutionApproval | None = None,
        llm_reasoner: ReasoningProvider | None = None,
        llm_evolution_kind: str = "workflow",
        llm_correction: str | None = None,
    ) -> AAWOTestTeamResult:
        if (
            evolution_approval is not None
            and evolution_proposal is None
            and llm_reasoner is None
        ):
            raise ValueError("evolution approval requires an evolution proposal")
        if evolution_proposal is not None and llm_reasoner is not None:
            raise ValueError("provide either an explicit evolution proposal or an LLM reasoner")
        if llm_reasoner is not None and llm_evolution_kind != "workflow":
            raise ValueError("AAWO runtime LLM application currently supports workflow proposals only")
        evolution_requested = evolution_proposal is not None or llm_reasoner is not None
        description = adapter.describe()
        if profile.adapter_id != description.adapter_id:
            raise ValueError(
                "profile adapter_id must match the exact under-test adapter boundary"
            )
        aawo = require_aawo_runtime()
        store = aawo.SQLiteDepartmentStore(
            self.aawo_store_path,
            durability="strict" if self.aawo_store_path != ":memory:" else "balanced",
        )
        pool = aawo.DepartmentPool(store)
        register_departments_with_aawo(pool)
        state = _ExecutionState(
            self.ledger,
            profile,
            journey,
            adapter,
            CustomerSimulationRunner(self.ledger),
        )
        blueprint_by_id: dict[str, TesterBlueprint] = {
            item.blueprint_id: item for item in default_test_blueprints()
        }
        for role_id in _EXECUTED_ROLE_IDS:
            blueprint = blueprint_by_id[role_id]
            pool.register_executor(
                blueprint.executor_name,
                _TestRoleExecutor(role_id, state, aawo),
            )
        director = blueprint_by_id["test-director"]
        pool.register_executor(
            director.executor_name,
            _RevisionAwareTeamExecutor(state, aawo),
        )
        optimizer_blueprint = blueprint_by_id["quality-evolution"]
        if evolution_requested:
            pool.register_executor(
                optimizer_blueprint.executor_name,
                _EvolutionOptimizerExecutor(aawo),
            )
        runtime = aawo.WorkforceOrchestrator(pool)
        scope = memory_scope or f"agent-test:{journey.scenario_id}:{uuid.uuid4().hex}"
        release_order: tuple[str, ...] = ()
        try:
            root = await runtime.start_team(aawo.RecruitmentRequest(
                objective=f"Govern customer-journey test {journey.scenario_id}",
                required_capabilities=frozenset({"test-orchestration"}),
                department_id="agent_test_control",
                blueprint_id="test-director",
                memory_scope=scope,
                context={
                    "scenario_id": journey.scenario_id,
                    "journey_revision": journey.revision,
                    "journey_digest": digest(journey.to_dict()),
                    "profile_revision": profile.revision,
                    "profile_digest": digest(profile.to_dict()),
                },
                acceptance_criteria=(
                    "Return the exact settled customer-journey status.",
                    "Preserve scoped evidence and independent reviews.",
                ),
                risk_level={
                    "read_only": "low",
                    "sandbox_write": "normal",
                    "human_approved_write": "high",
                }[journey.side_effect_policy],
            ))
            optimizer = None
            if evolution_requested:
                optimizer = await runtime.hire_child(root, aawo.RecruitmentRequest(
                    objective=(
                        "Propose evidence-backed tester workflow improvements "
                        "without applying them"
                    ),
                    required_capabilities=frozenset({
                        "quality-evolution",
                        "workflow_optimization",
                    }),
                    department_id="agent_test_evolution",
                    blueprint_id="quality-evolution",
                    acceptance_criteria=(
                        "Emit only revision-bound, evidence-backed proposals.",
                        "Never apply, approve or conceal a failed canary.",
                    ),
                    risk_level="high",
                ))
            workflow_data = journey_to_aawo_workflow_data(journey)
            if optimizer is not None:
                workflow_data["optimizer_agent_id"] = optimizer.agent_id
            workflow_seed = aawo.WorkflowSeed.from_dict(workflow_data)
            workflow = runtime.initialize_workflow(
                root.team_id,
                workflow_seed,
                objective=journey.goal,
            )
            team_leader = await runtime.hire_for_workflow_node(
                root,
                _WORKFLOW_NODE_ID,
            )
            result = await runtime.run(team_leader)
            test_run = state.require_run()
            workflow_status = runtime.workflow_node_status(root.team_id)
            if not workflow_status.get("all_completed"):
                raise RuntimeError("AAWO workflow did not reach a completed receipt boundary")
            evolution = None
            llm_proposal = None
            llm_proposal_error = None
            if evolution_requested:
                assert optimizer is not None
                runtime.finalize_subtree_summary(
                    root.team_id,
                    team_leader.agent_id,
                    finalized_by=team_leader.agent_id,
                )
                if llm_reasoner is not None:
                    try:
                        active_workflow = runtime.active_workflow(root.team_id)
                        llm_proposal = await llm_reasoner.propose_evolution(
                            agent_id=profile.agent_id,
                            kind=llm_evolution_kind,
                            base_revision=(
                                int(active_workflow.revision)
                                if active_workflow is not None
                                else 1
                            ),
                            contract=profile.to_dict(),
                            journey={
                                "customer_journey": journey.to_dict(),
                                "aawo_workflow": journey_to_aawo_workflow_data(journey),
                            },
                            evidence=_build_llm_evidence_context(state, test_run),
                            correction=llm_correction,
                        )
                        evolution_proposal = llm_proposal
                    except (ReasoningProviderError, ValueError, OSError) as exc:
                        llm_proposal_error = (
                            f"{type(exc).__name__}: {str(exc)[:300]}"
                        )
                        self.ledger.append(
                            f"llm-proposal-inconclusive:{test_run.run_id}",
                            "reasoning.proposal.inconclusive",
                            test_run.run_id,
                            {
                                "schema": "aawo.reasoning.proposal_inconclusive/v1",
                                "error_type": type(exc).__name__,
                                "error_detail": str(exc)[:300],
                                "model": getattr(llm_reasoner, "model", "configured"),
                            },
                        )
                if evolution_proposal is not None:
                    evolution = await _run_controlled_workflow_evolution(
                        aawo=aawo,
                        runtime=runtime,
                        root=root,
                        optimizer=optimizer,
                        state=state,
                        baseline_run=test_run,
                        proposal=evolution_proposal,
                        approval=evolution_approval,
                        memory_scope=scope,
                    )
                workflow_status = runtime.workflow_node_status(root.team_id)
            team_snapshot = runtime.team_snapshot(root.team_id)
            shutdown = await runtime.shutdown_team(root.team_id, aawo.ReleaseMode.IDLE)
            release_order = tuple(shutdown.release_order)
            team_result = dict(result.output)
            if llm_reasoner is not None:
                team_result["llm_proposal_status"] = (
                    "received" if llm_proposal is not None else "inconclusive"
                )
            return AAWOTestTeamResult(
                test_run=test_run,
                team_id=root.team_id,
                workflow_id=workflow.workflow_id,
                workflow_status=workflow_status,
                team_snapshot=team_snapshot,
                team_result=team_result,
                evidence_refs=tuple(state.evidence_refs),
                release_order=release_order,
                aawo_store_path=self.aawo_store_path,
                evolution=evolution,
                llm_proposal=llm_proposal,
                llm_proposal_error=llm_proposal_error,
            )
        finally:
            store.close()
