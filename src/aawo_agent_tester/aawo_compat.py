"""AAWO mapping without importing or copying the AAWO runtime."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class TesterBlueprint:
    blueprint_id: str
    role: str
    mission: str
    capabilities: tuple[str, ...]
    department_id: str = "agent_testing"

    @property
    def executor_name(self) -> str:
        """Return the immutable AAWO executor binding for this role."""
        return f"aawo_agent_tester.{self.blueprint_id}"

    def to_department_blueprint(self) -> dict[str, Any]:
        return {
            "blueprint_id": self.blueprint_id,
            "role": self.role,
            "mission": self.mission,
            "capabilities": list(self.capabilities),
            "tools": [],
            "executor": "aawo_agent_tester",
        }


def default_test_blueprints() -> tuple[TesterBlueprint, ...]:
    return (
        TesterBlueprint("test-director", "Test Director", "Own test scope, risk and final evidence-backed conclusion.", ("test-orchestration",), "agent_test_control"),
        TesterBlueprint("contract-miner", "Contract Miner", "Infer input/output and error contracts from declared and observed evidence.", ("contract-inference",), "agent_test_understanding"),
        TesterBlueprint("domain-interviewer", "Domain Interviewer", "Ask bounded clarification questions and record user corrections.", ("clarification",), "agent_test_understanding"),
        TesterBlueprint("customer-simulator", "Customer Simulator", "Execute confirmed customer journeys with role, data and permission context.", ("customer-journey",), "agent_test_execution"),
        TesterBlueprint("environment-operator", "Environment Operator", "Prepare fixtures, snapshots, reset and side-effect gates.", ("sandbox-operation",), "agent_test_execution"),
        TesterBlueprint("protocol-verifier", "Protocol Verifier", "Validate structure, status, errors, tools and transfer contracts.", ("contract-validation",), "agent_test_review"),
        TesterBlueprint("outcome-reviewer", "Outcome Reviewer", "Judge whether the customer goal was actually completed.", ("domain-outcome-review",), "agent_test_review"),
        TesterBlueprint("ux-friction-reviewer", "UX Friction Reviewer", "Identify evidence-bound human friction and recovery cost.", ("human-factors",), "agent_test_review"),
        TesterBlueprint("evidence-auditor", "Evidence Auditor", "Check provenance, hashes, scope and conclusion authority.", ("evidence-audit",), "agent_test_review"),
        TesterBlueprint(
            "quality-evolution",
            "Quality Evolution",
            "Propose versioned workflow and team improvements; never apply them directly.",
            ("quality-evolution", "workflow_optimization", "team_optimization"),
            "agent_test_evolution",
        ),
    )


_DEPARTMENT_METADATA: dict[str, tuple[str, str]] = {
    "agent_test_control": ("Agent Test Control", "Own test scope, authority, workflow and final settlement."),
    "agent_test_understanding": ("Agent Test Understanding", "Build evidence-bound contract hypotheses and clarification requests."),
    "agent_test_execution": ("Agent Test Execution", "Operate fixtures and execute customer journeys through controlled adapters."),
    "agent_test_review": ("Agent Test Review", "Review protocol, outcome, human friction and evidence integrity independently."),
    "agent_test_evolution": ("Agent Test Evolution", "Propose governed quality improvements without mutating registries directly."),
}


def build_aawo_department_dicts(
    blueprints: tuple[TesterBlueprint, ...] | None = None,
) -> tuple[dict[str, Any], ...]:
    """Build the strict multi-department AAWO registry projection.

    Departments express durable authority domains.  Test execution order stays
    in AAWO TeamExecutionSpec/AdaptiveWorkflow and is deliberately not encoded
    by the department grouping.
    """
    selected = blueprints or default_test_blueprints()
    grouped: dict[str, list[TesterBlueprint]] = {}
    for blueprint in selected:
        grouped.setdefault(blueprint.department_id, []).append(blueprint)
    unknown = set(grouped) - set(_DEPARTMENT_METADATA)
    if unknown:
        raise ValueError(f"unknown AAWO tester departments: {sorted(unknown)}")
    departments: list[dict[str, Any]] = []
    for department_id in _DEPARTMENT_METADATA:
        members = grouped.get(department_id, [])
        if not members:
            continue
        name, charter = _DEPARTMENT_METADATA[department_id]
        departments.append({
            "department_id": department_id,
            "name": name,
            "charter": charter,
            "blueprints": [
                item.to_department_blueprint() | {
                    "executor": item.executor_name,
                    "routing_tags": ["agent-test", item.blueprint_id],
                }
                for item in members
            ],
            "metadata": {
                "source": "aawo_agent_tester",
                "governance": "evidence_first",
                "topology": "authority_only",
            },
        })
    return tuple(departments)


def build_aawo_department_dict(
    blueprints: tuple[TesterBlueprint, ...] | None = None,
    *,
    department_id: str = "agent_testing",
) -> dict[str, Any]:
    """Build the dict accepted by ``aawo.DepartmentPool.register_department``.

    The bridge intentionally depends only on AAWO's public dict contract.  The
    AAWO package remains optional, so the P0 tester can run independently.
    """
    selected = blueprints or default_test_blueprints()
    return {
        "department_id": department_id,
        "name": "Agent Testing",
        "charter": "Understand and test Agents through customer journeys with durable evidence.",
        "blueprints": [item.to_department_blueprint() for item in selected],
        "metadata": {"source": "aawo_agent_tester", "governance": "evidence_first"},
    }


def register_with_aawo(pool: Any, *, blueprints: tuple[TesterBlueprint, ...] | None = None) -> dict[str, Any]:
    """Register the tester department into an existing AAWO DepartmentPool."""
    register = getattr(pool, "register_department", None)
    if not callable(register):
        raise TypeError("AAWO pool must expose register_department")
    department = build_aawo_department_dict(blueprints)
    register(department)
    return department


def register_departments_with_aawo(
    pool: Any,
    *,
    blueprints: tuple[TesterBlueprint, ...] | None = None,
) -> tuple[dict[str, Any], ...]:
    """Register the strict authority-separated tester departments in one batch."""
    departments = build_aawo_department_dicts(blueprints)
    register_many = getattr(pool, "register_departments", None)
    if callable(register_many):
        register_many(departments)
        return departments
    register_one = getattr(pool, "register_department", None)
    if not callable(register_one):
        raise TypeError("AAWO pool must expose register_departments or register_department")
    for department in departments:
        register_one(department)
    return departments
