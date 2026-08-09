from __future__ import annotations

import asyncio
import copy

import pytest

from aawo_agent_tester import (
    AAWOTestTeamRunner,
    AgentContractProfile,
    CallableAdapter,
    CustomerJourney,
    EvidenceLedger,
    EvolutionApproval,
    EvolutionProposal,
    JourneyStep,
    RunStatus,
    aawo_test_team_spec_data,
    build_aawo_department_dicts,
    journey_to_aawo_workflow_data,
)


def _profile() -> AgentContractProfile:
    return AgentContractProfile(
        "agent-aawo-integration",
        "callable-aawo-integration",
        purpose="return a customer-visible answer",
        output_schema={
            "type": "object",
            "required": ["answer", "reference"],
            "properties": {
                "answer": {"type": "string"},
                "reference": {"type": "string"},
            },
        },
    )


def _journey(*, side_effect_policy: str = "read_only") -> CustomerJourney:
    return CustomerJourney(
        "customer.aawo.integration.v1",
        "客户获得带引用的真实答案",
        (
            JourneyStep("ask", "user_input", {"question": "交付状态"}),
            JourneyStep(
                "verify",
                "expect",
                assertions=({
                    "kind": "contains_keys",
                    "keys": ["answer", "reference"],
                },),
            ),
        ),
        source="customer_trace",
        side_effect_policy=side_effect_policy,
        evidence_ids=("customer-trace-aawo-1",),
    )


def _workflow_evolution_proposal(
    ledger: EvidenceLedger,
    *,
    proposal_id: str,
) -> EvolutionProposal:
    evidence_id = f"{proposal_id}.user-correction"
    ledger.append(
        evidence_id,
        "correction.created",
        proposal_id,
        {
            "correction_id": evidence_id,
            "target": "workflow.acceptance",
            "reason": "Customer requires an explicit recovery-path audit.",
        },
    )
    definition = copy.deepcopy(
        journey_to_aawo_workflow_data(_journey())["definition"]
    )
    definition["work_nodes"][0]["objective"] += (
        " Re-run the full customer journey and preserve recovery evidence."
    )
    definition["work_nodes"][0]["acceptance_criteria"].append(
        "A fresh canary TestRun must settle independently from the baseline."
    )
    return EvolutionProposal(
        proposal_id,
        "workflow",
        1,
        {"definition": definition},
        (evidence_id,),
        risk="high",
    )


def _aawo_runtime_record(path, record_id: str):
    aawo = pytest.importorskip("aawo")
    store = aawo.SQLiteDepartmentStore(path)
    try:
        return store.runtime_record(record_id)
    finally:
        store.close()


def _aawo_active_workflow_record(path, team_id: str):
    aawo = pytest.importorskip("aawo")
    store = aawo.SQLiteDepartmentStore(path)
    try:
        records = store.runtime_records("adaptive_workflow", team_id=team_id)
        return next(item for item in records if item["status"] == "active")
    finally:
        store.close()


def test_strict_aawo_projection_separates_authority_workflow_and_team_roles():
    departments = build_aawo_department_dicts()
    assert [item["department_id"] for item in departments] == [
        "agent_test_control",
        "agent_test_understanding",
        "agent_test_execution",
        "agent_test_review",
        "agent_test_evolution",
    ]
    blueprints = [item for department in departments for item in department["blueprints"]]
    assert len(blueprints) == 10
    assert all(item["executor"].startswith("aawo_agent_tester.") for item in blueprints)

    workflow = journey_to_aawo_workflow_data(_journey())
    node = workflow["definition"]["work_nodes"][0]
    assert node["required_capabilities"] == ["test-orchestration"]
    assert node["max_attempts"] == 1
    assert node["failure_policy"] == "stop"
    assert "payload" not in workflow["definition"]["customer_journey"]

    team = aawo_test_team_spec_data()
    assert team["composition_id"] == "aawo-agent-customer-test/v1"
    assert {item["department_id"] for item in team["roles"]} == {
        "agent_test_understanding",
        "agent_test_execution",
        "agent_test_review",
    }


def test_real_aawo_team_tree_preserves_pass_and_scoped_evidence(tmp_path):
    pytest.importorskip("aawo")
    ledger = EvidenceLedger(tmp_path / "tester.sqlite3")
    adapter = CallableAdapter(
        "callable-aawo-integration",
        lambda payload: {
            "answer": f"answer:{payload['question']}",
            "reference": "customer-system-1",
        },
    )
    result = asyncio.run(AAWOTestTeamRunner(
        ledger,
        aawo_store_path=tmp_path / "aawo.sqlite3",
    ).run(_journey(), _profile(), adapter, memory_scope="tenant-a/project-a/test-a"))

    assert result.test_run.status is RunStatus.PASS
    assert result.team_result["status"] == "pass"
    assert result.workflow_status["all_completed"] is True
    assert result.workflow_status["nodes"]["execute_customer_journey_test"]["status"] == "completed"
    assert len(result.team_result["members"]) == 7
    assert len(result.evidence_refs) == 7
    assert all(item["team_id"] == result.team_id for item in result.evidence_refs)
    assert all(item["memory_scope"] == "tenant-a/project-a/test-a" for item in result.evidence_refs)
    assert all(len(item["content_digest"]) == 64 for item in result.evidence_refs)
    assert len(result.release_order) >= 2
    assert (tmp_path / "aawo.sqlite3").stat().st_size > 0
    assert ledger.verify_integrity(aggregate_id=result.test_run.run_id) == ()


def test_real_aawo_team_tree_keeps_side_effect_blocked_without_invocation(tmp_path):
    pytest.importorskip("aawo")
    calls: list[dict] = []

    def write_adapter(payload):
        calls.append(payload)
        return {"answer": "should-not-run", "reference": "none"}

    ledger = EvidenceLedger(tmp_path / "tester-blocked.sqlite3")
    adapter = CallableAdapter(
        "callable-aawo-integration",
        write_adapter,
        side_effect_policy="sandbox_write",
    )
    result = asyncio.run(AAWOTestTeamRunner(
        ledger,
        aawo_store_path=tmp_path / "aawo-blocked.sqlite3",
    ).run(_journey(), _profile(), adapter, memory_scope="tenant-a/project-a/test-blocked"))

    assert result.test_run.status is RunStatus.BLOCKED
    assert result.team_result["status"] == "blocked"
    assert result.workflow_status["all_completed"] is True
    assert calls == []
    assert not any(
        item["payload"].get("status") == "pass"
        for item in ledger.records(aggregate_id=result.test_run.run_id)
    )


def test_real_aawo_team_tree_does_not_promote_contract_failure(tmp_path):
    pytest.importorskip("aawo")
    ledger = EvidenceLedger(tmp_path / "tester-fail.sqlite3")
    adapter = CallableAdapter(
        "callable-aawo-integration",
        lambda _payload: {"answer": "missing required reference"},
    )
    result = asyncio.run(AAWOTestTeamRunner(
        ledger,
        aawo_store_path=tmp_path / "aawo-fail.sqlite3",
    ).run(_journey(), _profile(), adapter, memory_scope="tenant-a/project-a/test-fail"))

    assert result.test_run.status is RunStatus.FAIL
    assert result.team_result["status"] == "fail"
    assert result.workflow_status["all_completed"] is True
    assert any(
        item["payload"].get("kind") == "contract_violation"
        for item in ledger.records(
            record_type="finding.created",
            aggregate_id=result.test_run.run_id,
        )
    )
    assert not any(
        item["payload"].get("status") == "pass"
        for item in ledger.records(aggregate_id=result.test_run.run_id)
    )


def test_controlled_evolution_rejects_without_explicit_human_approval(tmp_path):
    pytest.importorskip("aawo")
    ledger = EvidenceLedger(tmp_path / "tester-evolution-rejected.sqlite3")
    proposal = _workflow_evolution_proposal(
        ledger,
        proposal_id="evolution-rejected",
    )
    result = asyncio.run(AAWOTestTeamRunner(
        ledger,
        aawo_store_path=tmp_path / "aawo-evolution-rejected.sqlite3",
    ).run(
        _journey(),
        _profile(),
        CallableAdapter(
            "callable-aawo-integration",
            lambda payload: {
                "answer": f"answer:{payload['question']}",
                "reference": "customer-system-1",
            },
        ),
        evolution_proposal=proposal,
        memory_scope="tenant-a/project-a/evolution-rejected",
    ))

    assert result.test_run.status is RunStatus.PASS
    assert result.evolution is not None
    assert result.evolution.status == "rejected"
    assert result.evolution.aawo_proposal_id is not None
    assert result.evolution.approval_id is not None
    assert result.evolution.canary_run is None
    assert result.evolution.final_workflow_revision == 1
    approval_record = _aawo_runtime_record(
        tmp_path / "aawo-evolution-rejected.sqlite3",
        result.evolution.approval_id,
    )
    assert approval_record is not None
    assert approval_record["status"] == "rejected"
    decisions = ledger.records(
        record_type="evolution.decision",
        aggregate_id=proposal.proposal_id,
    )
    assert [item["payload"]["decision"] for item in decisions] == ["rejected"]


def test_real_reasoner_boundary_can_feed_runner_but_no_approval_means_rejected(tmp_path):
    pytest.importorskip("aawo")

    class FakeReasoner:
        model = "test-real-reasoner-boundary"

        async def propose_evolution(
            self,
            *,
            agent_id,
            kind,
            base_revision,
            contract,
            journey,
            evidence,
            correction=None,
        ):
            assert agent_id == "agent-aawo-integration"
            assert kind == "workflow"
            assert base_revision == 1
            assert contract["agent_id"] == agent_id
            assert journey["customer_journey"]["scenario_id"] == "customer.aawo.integration.v1"
            assert correction is not None
            assert evidence
            definition = copy.deepcopy(journey["aawo_workflow"]["definition"])
            definition["work_nodes"][0]["objective"] += " Preserve LLM correction evidence."
            return EvolutionProposal(
                "llm-generated-workflow-proposal",
                "workflow",
                base_revision,
                {"definition": definition},
                (evidence[0]["evidence_id"],),
                risk="high",
            )

    ledger = EvidenceLedger(tmp_path / "tester-llm-boundary.sqlite3")
    calls = 0

    def agent(_payload):
        nonlocal calls
        calls += 1
        return {"answer": "confirmed", "reference": "system"}

    result = asyncio.run(AAWOTestTeamRunner(
        ledger,
        aawo_store_path=tmp_path / "aawo-llm-boundary.sqlite3",
    ).run(
        _journey(),
        _profile(),
        CallableAdapter("callable-aawo-integration", agent),
        memory_scope="test/llm-boundary",
        llm_reasoner=FakeReasoner(),
        llm_correction="客户要求保留 LLM 发现的验证步骤。",
    ))

    assert calls == 1
    assert result.llm_proposal is not None
    assert result.llm_proposal_error is None
    assert result.team_result["llm_proposal_status"] == "received"
    assert result.evolution is not None
    assert result.evolution.status == "rejected"
    ledger.close()


def test_controlled_evolution_promotes_only_after_real_customer_canary(tmp_path):
    pytest.importorskip("aawo")
    ledger = EvidenceLedger(tmp_path / "tester-evolution-promoted.sqlite3")
    proposal = _workflow_evolution_proposal(
        ledger,
        proposal_id="evolution-promoted",
    )
    calls: list[str] = []

    def stable_customer_agent(payload):
        calls.append(payload["question"])
        return {
            "answer": f"answer:{payload['question']}",
            "reference": "customer-system-1",
        }

    result = asyncio.run(AAWOTestTeamRunner(
        ledger,
        aawo_store_path=tmp_path / "aawo-evolution-promoted.sqlite3",
    ).run(
        _journey(),
        _profile(),
        CallableAdapter("callable-aawo-integration", stable_customer_agent),
        evolution_proposal=proposal,
        evolution_approval=EvolutionApproval(
            True,
            "human-quality-owner",
            "The customer correction is valid; run one isolated canary.",
            human_approved=True,
        ),
        memory_scope="tenant-a/project-a/evolution-promoted",
    ))

    assert calls == ["交付状态", "交付状态"], result.evolution
    assert result.test_run.status is RunStatus.PASS
    assert result.evolution is not None
    assert result.evolution.status == "promoted"
    assert result.evolution.rolled_back is False
    assert result.evolution.canary_run is not None
    assert result.evolution.canary_run.run_id != result.test_run.run_id
    assert result.evolution.canary_run.status is RunStatus.PASS
    assert result.evolution.metrics is not None
    assert result.evolution.metrics.accepted is True
    assert result.evolution.final_workflow_revision == 2
    assert result.workflow_status["all_completed"] is True
    assert len(result.evidence_refs) == 15
    approval_record = _aawo_runtime_record(
        tmp_path / "aawo-evolution-promoted.sqlite3",
        result.evolution.approval_id,
    )
    assert approval_record is not None
    assert approval_record["status"] == "approved"
    control_record = _aawo_runtime_record(
        tmp_path / "aawo-evolution-promoted.sqlite3",
        result.evolution.control_ledger_id,
    )
    assert control_record is not None
    assert control_record["status"] == "promoted"
    decisions = ledger.records(
        record_type="evolution.decision",
        aggregate_id=proposal.proposal_id,
    )
    assert [item["payload"]["decision"] for item in decisions] == [
        "shadow",
        "approved",
    ]


def test_harmful_evolution_is_frozen_and_rolled_back_by_aawo(tmp_path):
    pytest.importorskip("aawo")
    ledger = EvidenceLedger(tmp_path / "tester-evolution-frozen.sqlite3")
    proposal = _workflow_evolution_proposal(
        ledger,
        proposal_id="evolution-frozen",
    )
    call_count = 0

    def regressing_customer_agent(payload):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return {
                "answer": f"answer:{payload['question']}",
                "reference": "customer-system-1",
            }
        return {"answer": "candidate lost the required reference"}

    result = asyncio.run(AAWOTestTeamRunner(
        ledger,
        aawo_store_path=tmp_path / "aawo-evolution-frozen.sqlite3",
    ).run(
        _journey(),
        _profile(),
        CallableAdapter("callable-aawo-integration", regressing_customer_agent),
        evolution_proposal=proposal,
        evolution_approval=EvolutionApproval(
            True,
            "human-quality-owner",
            "Run the corrected workflow in a supervised canary.",
            human_approved=True,
        ),
        memory_scope="tenant-a/project-a/evolution-frozen",
    ))

    assert call_count == 2, result.evolution
    assert result.test_run.status is RunStatus.PASS
    assert result.evolution is not None
    assert result.evolution.status == "frozen"
    assert result.evolution.rolled_back is True
    assert result.evolution.canary_run is not None
    assert result.evolution.canary_run.status is RunStatus.FAIL
    assert result.evolution.metrics is not None
    assert result.evolution.metrics.verdict == "harmful"
    assert result.evolution.metrics.accepted is False
    assert result.evolution.base_workflow_revision == 1
    assert result.evolution.final_workflow_revision == 3
    assert result.workflow_status["all_completed"] is True
    control_record = _aawo_runtime_record(
        tmp_path / "aawo-evolution-frozen.sqlite3",
        result.evolution.control_ledger_id,
    )
    assert control_record is not None
    assert control_record["status"] == "frozen"
    workflow_record = _aawo_active_workflow_record(
        tmp_path / "aawo-evolution-frozen.sqlite3",
        result.team_id,
    )
    assert workflow_record["payload"]["revision"] == 3
    assert workflow_record["payload"]["history"][-1]["event_type"] == "rollback"
    assert workflow_record["payload"]["history"][-1]["restored_revision"] == 1
    decisions = ledger.records(
        record_type="evolution.decision",
        aggregate_id=proposal.proposal_id,
    )
    assert [item["payload"]["decision"] for item in decisions] == [
        "shadow",
        "rejected",
    ]


def test_non_executable_evolution_cannot_fake_a_canary(tmp_path):
    pytest.importorskip("aawo")
    ledger = EvidenceLedger(tmp_path / "tester-evolution-noop.sqlite3")
    evidence_id = "evolution-noop.user-correction"
    ledger.append(
        evidence_id,
        "correction.created",
        "evolution-noop",
        {"reason": "Request a team-level note without executable semantics."},
    )
    proposal = EvolutionProposal(
        "evolution-noop",
        "workflow",
        1,
        {"constraints": ["Record a final review decision."]},
        (evidence_id,),
    )
    calls = 0

    def stable_customer_agent(payload):
        nonlocal calls
        calls += 1
        return {
            "answer": f"answer:{payload['question']}",
            "reference": "customer-system-1",
        }

    result = asyncio.run(AAWOTestTeamRunner(
        ledger,
        aawo_store_path=tmp_path / "aawo-evolution-noop.sqlite3",
    ).run(
        _journey(),
        _profile(),
        CallableAdapter("callable-aawo-integration", stable_customer_agent),
        evolution_proposal=proposal,
        evolution_approval=EvolutionApproval(
            True,
            "human-quality-owner",
            "Check whether this produces a real canary.",
            human_approved=True,
        ),
        memory_scope="tenant-a/project-a/evolution-noop",
    ))

    assert calls == 1
    assert result.evolution is not None
    assert result.evolution.status == "frozen"
    assert result.evolution.canary_run is None
    assert result.evolution.rolled_back is True
    assert result.evolution.final_workflow_revision == 3


def test_non_workflow_evolution_remains_proposal_only(tmp_path):
    pytest.importorskip("aawo")
    ledger = EvidenceLedger(tmp_path / "tester-evolution-proposal-only.sqlite3")
    evidence_id = "evolution-evaluator.user-correction"
    ledger.append(
        evidence_id,
        "correction.created",
        "evolution-evaluator",
        {"reason": "User corrected an evaluator interpretation."},
    )
    proposal = EvolutionProposal(
        "evolution-evaluator",
        "evaluator",
        1,
        {"rule": "require a domain-specific reference"},
        (evidence_id,),
        risk="high",
    )
    result = asyncio.run(AAWOTestTeamRunner(
        ledger,
        aawo_store_path=tmp_path / "aawo-evolution-proposal-only.sqlite3",
    ).run(
        _journey(),
        _profile(),
        CallableAdapter(
            "callable-aawo-integration",
            lambda payload: {
                "answer": f"answer:{payload['question']}",
                "reference": "customer-system-1",
            },
        ),
        evolution_proposal=proposal,
        evolution_approval=EvolutionApproval(
            True,
            "human-quality-owner",
            "Keep this correction for a future registry implementation.",
            human_approved=True,
        ),
        memory_scope="tenant-a/project-a/evolution-proposal-only",
    ))

    assert result.evolution is not None
    assert result.evolution.status == "rejected"
    assert result.evolution.aawo_proposal_id is None
    assert result.evolution.approval_id is None
    assert result.evolution.canary_run is None
    assert ledger.records(
        record_type="evolution.proposal",
        aggregate_id=proposal.proposal_id,
    )
