"""Correction impact analysis and evidence-bound minimum regression execution."""
from __future__ import annotations

import uuid
from collections.abc import Iterable

from .adapters import UnderTestAdapter
from .ledger import EvidenceLedger
from .models import (
    AgentContractProfile,
    Correction,
    CustomerJourney,
    RegressionPlan,
    TestRun,
)
from .runner import CustomerSimulationRunner


class CorrectionImpactAnalyzer:
    def __init__(self, ledger: EvidenceLedger) -> None:
        self.ledger = ledger

    def plan(
        self,
        correction: Correction,
        journeys: Iterable[CustomerJourney],
    ) -> RegressionPlan:
        known = {journey.scenario_id: journey for journey in journeys}
        if not known:
            raise ValueError("at least one customer journey is required")
        missing = set(correction.regression_scenarios) - set(known)
        if missing:
            raise KeyError(f"correction references unknown scenarios: {sorted(missing)}")

        selected: set[str] = set(correction.regression_scenarios)
        reasons: list[str] = []
        if selected:
            reasons.append("correction_explicit_regression_scope_overrides_inference")

        target_root = correction.target.split(".", 1)[0]
        if not selected:
            for scenario_id, journey in known.items():
                if set(journey.evidence_ids).intersection(correction.evidence_ids):
                    selected.add(scenario_id)
                    reasons.append("shared_evidence")
                if target_root in {"input_schema", "output_schema", "error_schema"}:
                    if any(step.kind == "user_input" for step in journey.steps):
                        selected.add(scenario_id)
                        reasons.append(f"{target_root}_affects_agent_interaction")
                elif target_root in {"tools", "side_effect_policy", "session_model"}:
                    if any(step.kind in {"user_input", "reset"} for step in journey.steps):
                        selected.add(scenario_id)
                        reasons.append(f"{target_root}_affects_runtime_behavior")

        if not selected:
            selected.update(known)
            reasons.append("unknown_contract_path_conservative_fallback")

        plan = RegressionPlan(
            plan_id=f"regression_{uuid.uuid4().hex}",
            correction_id=correction.correction_id,
            selected_scenario_ids=tuple(sorted(selected)),
            affected_paths=(correction.target,),
            reasons=tuple(dict.fromkeys(reasons)),
        )
        self.ledger.append(plan.plan_id, "regression.plan", correction.correction_id, plan.to_dict())
        return plan

    async def execute(
        self,
        plan: RegressionPlan,
        profile: AgentContractProfile,
        journeys: Iterable[CustomerJourney],
        adapter: UnderTestAdapter,
        runner: CustomerSimulationRunner,
    ) -> tuple[TestRun, ...]:
        by_id = {journey.scenario_id: journey for journey in journeys}
        missing = set(plan.selected_scenario_ids) - set(by_id)
        if missing:
            raise KeyError(f"regression plan references unknown scenarios: {sorted(missing)}")
        runs: list[TestRun] = []
        self.ledger.append(
            f"{plan.plan_id}_started",
            "regression.status",
            plan.plan_id,
            {"status": "running", "selected_scenario_ids": list(plan.selected_scenario_ids)},
        )
        for scenario_id in plan.selected_scenario_ids:
            runs.append(await runner.run(by_id[scenario_id], profile, adapter))
        self.ledger.append(
            f"{plan.plan_id}_completed",
            "regression.status",
            plan.plan_id,
            {
                "status": "completed",
                "run_ids": [run.run_id for run in runs],
                "run_statuses": [run.status.value for run in runs],
            },
        )
        return tuple(runs)
