"""Codex-powered customer simulation and implementation-completeness review.

Codex decides how a real customer would exercise an unfamiliar Agent and how
to interpret evidence.  It does not execute the target directly and it does
not settle results.  Every proposed journey is parsed and run by the existing
deterministic ``CustomerSimulationRunner``; missing coverage is reported as a
defect instead of being filled with synthetic or random tests.
"""
from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass
from typing import Any, Mapping

from .adapters import AdapterDescription, UnderTestAdapter
from .ledger import EvidenceLedger
from .models import AgentContractProfile, CustomerJourney, JourneyStep, RunStatus, TestRun
from .reasoning import ReasoningProvider, ReasoningProviderError
from .runner import CustomerSimulationRunner


SUPPORTED_ASSERTIONS = {"contains_keys", "text_contains", "status_is", "path_equals", "no_error"}
SUPPORTED_STEP_KINDS = {"user_input", "expect", "observe", "reset"}
MINIMUM_COVERAGE = (
    "normal_success",
    "invalid_or_incomplete_input",
    "output_contract",
    "failure_recovery",
    "repeated_input_or_correction",
)

_STRING_LIST_SCHEMA = {"type": "array", "items": {"type": "string"}}
_JSON_STRING_SCHEMA = {"type": "string"}

_ASSERTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["kind", "keys", "text", "status", "path", "value_json"],
    "properties": {
        "kind": {"type": "string", "enum": sorted(SUPPORTED_ASSERTIONS)},
        "keys": _STRING_LIST_SCHEMA,
        "text": {"type": "string"},
        "status": {"type": "string"},
        "path": {"type": "string"},
        "value_json": _JSON_STRING_SCHEMA,
    },
    "additionalProperties": False,
}

_STEP_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["step_id", "kind", "payload_json", "assertions"],
    "properties": {
        "step_id": {"type": "string"},
        "kind": {"type": "string", "enum": sorted(SUPPORTED_STEP_KINDS)},
        "payload_json": _JSON_STRING_SCHEMA,
        "assertions": {"type": "array", "items": _ASSERTION_SCHEMA},
    },
    "additionalProperties": False,
}

_JOURNEY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["scenario_id", "goal", "coverage_dimensions", "steps"],
    "properties": {
        "scenario_id": {"type": "string"},
        "goal": {"type": "string"},
        "coverage_dimensions": _STRING_LIST_SCHEMA,
        "steps": {"type": "array", "items": _STEP_SCHEMA},
    },
    "additionalProperties": False,
}

_TOOL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["name", "description", "input_schema_json"],
    "properties": {
        "name": {"type": "string"},
        "description": {"type": "string"},
        "input_schema_json": _JSON_STRING_SCHEMA,
    },
    "additionalProperties": False,
}

_PROFILE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["agent_id", "purpose", "input_schema_json", "output_schema_json", "error_schema_json"],
    "properties": {
        "agent_id": {"type": "string"},
        "purpose": {"type": "string"},
        "input_schema_json": _JSON_STRING_SCHEMA,
        "output_schema_json": _JSON_STRING_SCHEMA,
        "error_schema_json": _JSON_STRING_SCHEMA,
    },
    "additionalProperties": False,
}

_CHECK_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["check_id", "dimension", "scenario_ids", "capabilities"],
    "properties": {
        "check_id": {"type": "string"},
        "dimension": {"type": "string"},
        "scenario_ids": _STRING_LIST_SCHEMA,
        "capabilities": _STRING_LIST_SCHEMA,
    },
    "additionalProperties": False,
}

DISCOVERY_PLAN_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["profile", "journeys", "completeness_checks", "limitations"],
    "properties": {
        "profile": _PROFILE_SCHEMA,
        "journeys": {"type": "array", "items": _JOURNEY_SCHEMA},
        "completeness_checks": {"type": "array", "items": _CHECK_SCHEMA},
        "limitations": _STRING_LIST_SCHEMA,
    },
    "additionalProperties": False,
}

_FINDING_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["title", "severity", "kind", "detail", "evidence_ids", "step_id"],
    "properties": {
        "title": {"type": "string"},
        "severity": {"type": "string"},
        "kind": {"type": "string"},
        "detail": {"type": "string"},
        "evidence_ids": _STRING_LIST_SCHEMA,
        "step_id": {"type": "string"},
    },
    "additionalProperties": False,
}

REVIEW_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["summary", "findings", "missing_coverage"],
    "properties": {
        "summary": {"type": "string"},
        "findings": {"type": "array", "items": _FINDING_SCHEMA},
        "missing_coverage": _STRING_LIST_SCHEMA,
    },
    "additionalProperties": False,
}


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return str(value)


def build_discovery_messages(
    *,
    target: Mapping[str, Any],
    customer_goal: str,
    declared_capabilities: tuple[str, ...] = (),
    declared_contract: Mapping[str, Any] | None = None,
) -> tuple[dict[str, str], ...]:
    """Create a customer-oriented discovery prompt for one Codex thread."""
    context = {
        "target": _json_safe(dict(target)),
        "customer_goal": customer_goal,
        "declared_capabilities": list(declared_capabilities),
        "declared_contract": _json_safe(dict(declared_contract or {})),
        "required_coverage_dimensions": list(MINIMUM_COVERAGE),
        "supported_step_kinds": sorted(SUPPORTED_STEP_KINDS),
        "supported_assertions": sorted(SUPPORTED_ASSERTIONS),
        "completeness_check_fields": ["dimension", "scenario_ids", "capabilities", "question", "required"],
    }
    system = (
        "Act as a real customer and a skeptical acceptance tester for an unfamiliar Agent. "
        "Design realistic journeys around the supplied customer goal, not random fuzzing and "
        "not a health-ping-only test. Discover the input/output contract from declared facts "
        "and observed evidence. Include normal use, incomplete or invalid input, contract "
        "checks, failure recovery, and a repeated-input or correction path. Add a side-effect "
        "journey only when the target is explicitly isolated or approved. "
        "Return exactly one JSON object matching the output schema. Every journey must include "
        "coverage_dimensions, at least one user_input step, and explicit expect/observe steps. "
        "Do not claim a capability is implemented merely because it is declared; map each "
        "capability in a completeness check's capabilities list, map it to an executed journey, "
        "and leave unsupported or unverified items in limitations."
    )
    return (
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps(context, ensure_ascii=False, sort_keys=True)},
    )


def build_dimension_messages(
    *,
    target: Mapping[str, Any],
    customer_goal: str,
    dimension: str,
    declared_capabilities: tuple[str, ...] = (),
    declared_contract: Mapping[str, Any] | None = None,
) -> tuple[dict[str, str], ...]:
    """Build a compact one-dimension discovery turn for the real Codex SDK.

    A single five-journey structured turn can exceed a local Codex turn's
    practical latency.  Real SDK calls therefore discover one customer
    dimension at a time and the deterministic layer merges them; injected
    test reasoners may still use the full-plan prompt.
    """
    context = {
        "target": _json_safe(dict(target)),
        "customer_goal": customer_goal,
        "requested_dimension": dimension,
        "declared_capabilities": list(declared_capabilities),
        "declared_contract": _json_safe(dict(declared_contract or {})),
    }
    system = (
        "Act as a real customer testing an unfamiliar Agent. Produce the smallest valid "
        "Codex customer-test plan for exactly one requested coverage dimension. Return one "
        "journey and one completeness check for that dimension; do not add other dimensions. "
        "Use the supplied strict JSON schema. Keep payloads and discovered schemas as JSON "
        "strings. The journey must contain one realistic user_input and one expect/observe "
        "step. Do not invent capabilities or claim implementation without evidence."
    )
    return (
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps(context, ensure_ascii=False, sort_keys=True)},
    )


def build_review_messages(
    *,
    plan: Mapping[str, Any],
    runs: tuple[Mapping[str, Any], ...],
    capabilities: tuple[str, ...],
) -> tuple[dict[str, str], ...]:
    context = {
        "plan": _json_safe(dict(plan)),
        "runs": _json_safe(list(runs)),
        "declared_capabilities": list(capabilities),
        "rule": (
            "A run status is authoritative only from deterministic execution. Review findings "
            "must cite supplied evidence IDs; missing evidence or missing coverage is not a pass."
        ),
    }
    system = (
        "Review a customer-simulation test report as a skeptical product owner. Find concrete "
        "customer-visible defects, contract mismatches, misleading success, hostile workflows, "
        "missing implementation evidence, and untested capabilities. Do not rewrite or repair "
        "a failed run. Return one JSON object with summary, findings, and missing_coverage. "
        "Each finding should contain title, severity, kind, detail, and evidence_ids. Use only "
        "evidence IDs present in the supplied runs; if there is no evidence, put the item in "
        "missing_coverage instead."
    )
    return (
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps(context, ensure_ascii=False, sort_keys=True)},
    )


@dataclass(frozen=True)
class CodexTestPlan:
    plan_id: str
    profile: AgentContractProfile
    journeys: tuple[CustomerJourney, ...]
    completeness_checks: tuple[dict[str, Any], ...]
    limitations: tuple[str, ...]
    response_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "profile": self.profile.to_dict(),
            "journeys": [item.to_dict() for item in self.journeys],
            "completeness_checks": [_json_safe(item) for item in self.completeness_checks],
            "limitations": list(self.limitations),
            "response_id": self.response_id,
        }


@dataclass(frozen=True)
class CoverageResult:
    dimension: str
    status: str
    scenario_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self) | {
            "scenario_ids": list(self.scenario_ids),
            "evidence_ids": list(self.evidence_ids),
        }


@dataclass(frozen=True)
class CodexReview:
    status: str
    summary: str
    findings: tuple[dict[str, Any], ...]
    missing_coverage: tuple[str, ...]
    response_id: str | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "summary": self.summary,
            "findings": [_json_safe(item) for item in self.findings],
            "missing_coverage": list(self.missing_coverage),
            "response_id": self.response_id,
            "error": self.error,
        }


@dataclass(frozen=True)
class CodexTestReport:
    report_id: str
    target: dict[str, Any]
    plan: CodexTestPlan | None
    runs: tuple[TestRun, ...]
    coverage: tuple[CoverageResult, ...]
    review: CodexReview
    status: str
    limitations: tuple[str, ...]
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "codex.agent_customer_test_report/v1",
            "report_id": self.report_id,
            "target": _json_safe(self.target),
            "plan": self.plan.to_dict() if self.plan else None,
            "runs": [item.to_dict() for item in self.runs],
            "coverage": [item.to_dict() for item in self.coverage],
            "review": self.review.to_dict(),
            "status": self.status,
            "limitations": list(self.limitations),
            "error": self.error,
        }


class CodexCustomerTester:
    """Run Codex-planned customer journeys through deterministic adapters."""

    def __init__(self, ledger: EvidenceLedger, reasoner: ReasoningProvider) -> None:
        self.ledger = ledger
        self.reasoner = reasoner
        self.runner = CustomerSimulationRunner(ledger)

    async def test(
        self,
        adapter: UnderTestAdapter,
        *,
        target: Mapping[str, Any],
        customer_goal: str,
        declared_capabilities: tuple[str, ...] = (),
        declared_contract: Mapping[str, Any] | None = None,
    ) -> CodexTestReport:
        report_id = f"codex_report_{uuid.uuid4().hex}"
        target_data = _json_safe(dict(target))
        if not isinstance(target_data, dict):
            target_data = {"target": str(target_data)}
        target_data.setdefault("adapter", asdict(adapter.describe()))
        self.ledger.append(
            f"{report_id}_created",
            "codex.test.created",
            report_id,
            {"report_id": report_id, "target": target_data, "customer_goal": customer_goal},
        )
        try:
            if getattr(self.reasoner, "supports_dimension_planning", False):
                plan = await self._discover_dimensionwise(
                    target=target_data,
                    customer_goal=customer_goal,
                    declared_capabilities=declared_capabilities,
                    declared_contract=declared_contract,
                    adapter=adapter.describe(),
                )
            else:
                response = await self.reasoner.complete(
                    build_discovery_messages(
                        target=target_data,
                        customer_goal=customer_goal,
                        declared_capabilities=declared_capabilities,
                        declared_contract=declared_contract,
                    ),
                    response_schema=DISCOVERY_PLAN_SCHEMA,
                )
                plan = self._parse_plan(response.json_object(), response.response_id, adapter.describe())
        except Exception as exc:
            reason = str(exc)
            self.ledger.append(
                f"{report_id}_blocked",
                "codex.test.blocked",
                report_id,
                {"error_type": type(exc).__name__, "detail": reason},
            )
            return CodexTestReport(
                report_id,
                target_data,
                None,
                (),
                (),
                CodexReview("inconclusive", "Codex could not produce a validated test plan.", (), (), error=reason),
                "blocked",
                ("No deterministic journey was executed because the Codex plan was invalid or unavailable.",),
                reason,
            )

        self.ledger.append(f"{report_id}_plan", "codex.plan.created", report_id, plan.to_dict())
        runs: list[TestRun] = []
        for journey in plan.journeys:
            runs.append(await self.runner.run(journey, plan.profile, adapter))
        coverage = self._coverage(plan, runs, declared_capabilities)
        review = await self._review(plan, runs, coverage, declared_capabilities)
        status = self._settle_status(runs, coverage, review)
        limitations = tuple(dict.fromkeys(plan.limitations + self._coverage_limitations(coverage)))
        report = CodexTestReport(
            report_id,
            target_data,
            plan,
            tuple(runs),
            tuple(coverage),
            review,
            status,
            limitations,
        )
        self.ledger.append(f"{report_id}_settled", "codex.test.settled", report_id, report.to_dict())
        return report

    async def _discover_dimensionwise(
        self,
        *,
        target: Mapping[str, Any],
        customer_goal: str,
        declared_capabilities: tuple[str, ...],
        declared_contract: Mapping[str, Any] | None,
        adapter: AdapterDescription,
    ) -> CodexTestPlan:
        parts: list[CodexTestPlan] = []
        for dimension in MINIMUM_COVERAGE:
            response = await self.reasoner.complete(
                build_dimension_messages(
                    target=target,
                    customer_goal=customer_goal,
                    dimension=dimension,
                    declared_capabilities=declared_capabilities,
                    declared_contract=declared_contract,
                ),
                response_schema=DISCOVERY_PLAN_SCHEMA,
            )
            part = self._parse_plan(response.json_object(), response.response_id, adapter)
            if not any(
                dimension.lower() == str(check["dimension"]).lower()
                for check in part.completeness_checks
            ):
                raise ReasoningProviderError(
                    f"Codex dimension turn did not return the requested coverage: {dimension}"
                )
            parts.append(part)
        initial_profile = parts[0].profile
        conflicts: list[str] = []

        def merged_value(field: str) -> Any:
            values = [getattr(item.profile, field) for item in parts]
            if any(value != values[0] for value in values[1:]):
                conflicts.append(field)
            return values[0]

        profile = AgentContractProfile(
            agent_id=initial_profile.agent_id,
            adapter_id=adapter.adapter_id,
            purpose=initial_profile.purpose,
            input_schema=merged_value("input_schema"),
            output_schema=merged_value("output_schema"),
            error_schema=merged_value("error_schema"),
            tools=initial_profile.tools,
        )
        journeys: list[CustomerJourney] = []
        checks: list[dict[str, Any]] = []
        limitations: list[str] = []
        seen_scenarios: set[str] = set()
        seen_checks: set[tuple[str, tuple[str, ...]]] = set()
        response_ids: list[str] = []
        for part in parts:
            response_ids.append(part.response_id)
            for journey in part.journeys:
                if journey.scenario_id in seen_scenarios:
                    raise ReasoningProviderError(
                        f"Codex dimension turns returned duplicate scenario ID: {journey.scenario_id}"
                    )
                seen_scenarios.add(journey.scenario_id)
                journeys.append(journey)
            for check in part.completeness_checks:
                key = (str(check["dimension"]).lower(), tuple(check["scenario_ids"]))
                if key not in seen_checks:
                    seen_checks.add(key)
                    checks.append(check)
            limitations.extend(part.limitations)
        if conflicts:
            limitations.append(
                "Codex dimension turns produced conflicting contract hypotheses for: "
                + ", ".join(conflicts)
                + "; the conflicting fields remain unconfirmed."
            )
        self._validate_plan_quality(tuple(journeys), tuple(checks))
        return CodexTestPlan(
            plan_id=f"plan_{uuid.uuid4().hex}",
            profile=profile,
            journeys=tuple(journeys),
            completeness_checks=tuple(checks),
            limitations=tuple(dict.fromkeys(limitations)),
            response_id="dimensionwise:" + ",".join(response_ids),
        )

    def _parse_plan(
        self,
        payload: Mapping[str, Any],
        response_id: str,
        adapter: AdapterDescription,
    ) -> CodexTestPlan:
        profile_data = payload.get("profile")
        raw_journeys = payload.get("journeys")
        checks = payload.get("completeness_checks")
        if not isinstance(profile_data, Mapping) or not isinstance(raw_journeys, list) or not raw_journeys:
            raise ReasoningProviderError("Codex plan must contain a profile and at least one journey")
        if not isinstance(checks, list):
            raise ReasoningProviderError("Codex plan completeness_checks must be a list")
        profile = AgentContractProfile(
            agent_id=str(profile_data.get("agent_id") or "codex-discovered-agent"),
            adapter_id=adapter.adapter_id,
            purpose=str(profile_data.get("purpose") or ""),
            input_schema=_schema_or_none(profile_data.get("input_schema_json", profile_data.get("input_schema"))),
            output_schema=_schema_or_none(profile_data.get("output_schema_json", profile_data.get("output_schema"))),
            error_schema=_schema_or_none(profile_data.get("error_schema_json", profile_data.get("error_schema"))),
            tools=tuple(item for item in profile_data.get("tools", ()) if isinstance(item, Mapping)),
        )
        journeys = tuple(self._parse_journey(item) for item in raw_journeys)
        if len({item.scenario_id for item in journeys}) != len(journeys):
            raise ReasoningProviderError("Codex plan contains duplicate scenario IDs")
        normalized_checks = tuple(self._parse_check(item) for item in checks)
        self._validate_plan_quality(journeys, normalized_checks)
        return CodexTestPlan(
            plan_id=f"plan_{uuid.uuid4().hex}",
            profile=profile,
            journeys=journeys,
            completeness_checks=normalized_checks,
            limitations=tuple(str(item) for item in payload.get("limitations", ()) if str(item).strip()),
            response_id=response_id,
        )

    @staticmethod
    def _parse_journey(item: Any) -> CustomerJourney:
        if not isinstance(item, Mapping):
            raise ReasoningProviderError("each Codex journey must be an object")
        steps_data = item.get("steps")
        if not isinstance(steps_data, list) or not steps_data:
            raise ReasoningProviderError("each Codex journey must contain steps")
        steps: list[JourneyStep] = []
        for raw_step in steps_data:
            if not isinstance(raw_step, Mapping):
                raise ReasoningProviderError("Codex journey step must be an object")
            kind = str(raw_step.get("kind") or "")
            if kind not in SUPPORTED_STEP_KINDS:
                raise ReasoningProviderError(f"unsupported Codex journey step kind: {kind!r}")
            # A user-input step normally has no assertions.  Treat an omitted
            # field as an empty JSON list; rejecting it as a tuple would make
            # otherwise valid Codex plans fail closed for a serialization
            # detail rather than a real contract problem.
            assertions = raw_step.get("assertions", [])
            if not isinstance(assertions, list):
                raise ReasoningProviderError("journey assertions must be a list")
            normalized_assertions: list[dict[str, Any]] = []
            for assertion in assertions:
                if not isinstance(assertion, Mapping) or assertion.get("kind") not in SUPPORTED_ASSERTIONS:
                    raise ReasoningProviderError("journey contains an unsupported assertion")
                normalized = dict(assertion)
                if "value_json" in normalized:
                    encoded_value = normalized["value_json"]
                    if isinstance(encoded_value, str) and encoded_value.strip():
                        normalized["value"] = _decode_jsonish(encoded_value, "assertion.value_json")
                    elif normalized.get("kind") == "path_equals":
                        raise ReasoningProviderError("path_equals assertion needs a JSON value")
                normalized_assertions.append(normalized)
            steps.append(
                JourneyStep(
                    step_id=str(raw_step.get("step_id") or raw_step.get("id") or ""),
                    kind=kind,
                    payload=_decode_jsonish(
                        raw_step.get("payload_json", raw_step.get("payload")),
                        "step.payload_json",
                    ),
                    assertions=tuple(normalized_assertions),
                    description=str(raw_step.get("description") or ""),
                )
            )
        if not any(item.kind == "user_input" for item in steps):
            raise ReasoningProviderError("each Codex journey must include a user_input step")
        if not any(item.kind in {"expect", "observe"} for item in steps):
            raise ReasoningProviderError("each Codex journey must include an expect or observe step")
        dimensions = item.get("coverage_dimensions")
        if not isinstance(dimensions, list) or not dimensions:
            raise ReasoningProviderError("each journey must declare coverage_dimensions")
        return CustomerJourney(
            scenario_id=str(item.get("scenario_id") or ""),
            goal=str(item.get("goal") or ""),
            steps=tuple(steps),
            actor=_mapping_or_empty(
                item.get("actor_json", item.get("actor")),
                "journey.actor_json",
            ),
            preconditions=tuple(str(value) for value in item.get("preconditions", ()) if str(value).strip()),
            side_effect_policy=str(item.get("side_effect_policy") or "read_only"),
            source="codex_customer_simulation",
            evidence_ids=tuple(str(value) for value in item.get("evidence_ids", ()) if str(value).strip()),
            coverage_dimensions=tuple(str(value) for value in dimensions if str(value).strip()),
        )

    @staticmethod
    def _parse_check(item: Any) -> dict[str, Any]:
        if not isinstance(item, Mapping):
            raise ReasoningProviderError("completeness check must be an object")
        dimension = str(item.get("dimension") or "").strip()
        scenario_ids = item.get("scenario_ids")
        if not dimension or not isinstance(scenario_ids, list):
            raise ReasoningProviderError("completeness check needs dimension and scenario_ids")
        capabilities = item.get("capabilities", [])
        if not isinstance(capabilities, list):
            raise ReasoningProviderError("completeness check capabilities must be a list")
        return {
            "check_id": str(item.get("check_id") or f"check_{uuid.uuid4().hex[:8]}"),
            "dimension": dimension,
            "scenario_ids": tuple(str(value) for value in scenario_ids if str(value).strip()),
            "question": str(item.get("question") or dimension),
            "required": bool(item.get("required", True)),
            "capabilities": tuple(str(value) for value in capabilities if str(value).strip()),
        }

    @staticmethod
    def _validate_plan_quality(
        journeys: tuple[CustomerJourney, ...],
        checks: tuple[dict[str, Any], ...],
    ) -> None:
        """Reject shallow plans before they can manufacture a green report."""
        by_id = {journey.scenario_id: journey for journey in journeys}
        if not checks:
            raise ReasoningProviderError("Codex plan must contain at least one completeness check")
        for check in checks:
            scenario_ids = tuple(check["scenario_ids"])
            if not scenario_ids:
                raise ReasoningProviderError(
                    f"completeness check {check['check_id']!r} must map to a scenario"
                )
            unknown = sorted(set(scenario_ids) - set(by_id))
            if unknown:
                raise ReasoningProviderError(
                    f"completeness check {check['check_id']!r} references unknown scenarios: {unknown}"
                )
        for journey in journeys:
            text = " ".join(
                [
                    journey.goal,
                    *journey.preconditions,
                    *(step.description for step in journey.steps),
                    *(
                        json.dumps(step.payload, ensure_ascii=False, sort_keys=True)
                        for step in journey.steps
                        if step.kind == "user_input"
                    ),
                ]
            ).lower()
            user_inputs = [step for step in journey.steps if step.kind == "user_input"]
            assertions = [
                assertion
                for step in journey.steps
                if step.kind in {"expect", "observe"}
                for assertion in step.assertions
            ]
            for dimension in journey.coverage_dimensions:
                normalized = dimension.lower()
                if normalized == "output_contract" and not assertions:
                    raise ReasoningProviderError(
                        f"journey {journey.scenario_id!r} claims output_contract without an assertion"
                    )
                if normalized == "repeated_input_or_correction":
                    if len(user_inputs) < 2 and not _contains_any(
                        text, ("repeat", "retry", "correction", "纠正", "重复", "重试")
                    ):
                        raise ReasoningProviderError(
                            f"journey {journey.scenario_id!r} is not a repeated-input or correction path"
                        )
                if normalized == "failure_recovery":
                    if (
                        len(user_inputs) < 2
                        and not any(step.kind == "reset" for step in journey.steps)
                        and not _contains_any(
                            text, ("recover", "recovery", "retry", "failure", "失败", "恢复", "重试")
                        )
                    ):
                        raise ReasoningProviderError(
                            f"journey {journey.scenario_id!r} is not a failure-recovery path"
                        )
                if normalized == "invalid_or_incomplete_input":
                    has_empty_payload = any(_contains_empty_value(step.payload) for step in user_inputs)
                    if not has_empty_payload and not _contains_any(
                        text,
                        ("invalid", "incomplete", "missing", "empty", "wrong", "错误", "不完整", "缺少", "空"),
                    ):
                        raise ReasoningProviderError(
                            f"journey {journey.scenario_id!r} does not exercise invalid or incomplete input"
                        )

    def _coverage(
        self,
        plan: CodexTestPlan,
        runs: list[TestRun],
        capabilities: tuple[str, ...],
    ) -> list[CoverageResult]:
        run_by_scenario = {run.scenario_id: run for run in runs}
        result: list[CoverageResult] = []
        checks = list(plan.completeness_checks)
        declared_dimensions = {str(item["dimension"]).lower() for item in checks}
        if any("conflicting contract hypotheses" in item for item in plan.limitations):
            result.append(
                CoverageResult(
                    "contract_discovery",
                    "inconclusive",
                    tuple(run.scenario_id for run in runs),
                    tuple(),
                    "Codex dimension turns disagreed about the Agent contract; it remains unconfirmed.",
                )
            )
        if plan.profile.output_schema is None:
            result.append(
                CoverageResult(
                    "output_contract",
                    "inconclusive",
                    tuple(run.scenario_id for run in runs),
                    tuple(),
                    "No confirmed output schema was discovered; observed assertions cannot be promoted to a complete contract.",
                )
            )
        for required in MINIMUM_COVERAGE:
            if required.lower() not in declared_dimensions:
                result.append(CoverageResult(required, "missing", (), (), "Codex did not map this required customer dimension to a journey."))
        for check in checks:
            scenario_ids = tuple(check["scenario_ids"])
            selected = [run_by_scenario[item] for item in scenario_ids if item in run_by_scenario]
            evidence_ids = tuple(
                evidence_id
                for run in selected
                for step in run.step_results
                for evidence_id in step.evidence_ids
            )
            if not selected:
                state = "missing"
                detail = "No planned scenario was executed for this completeness check."
            elif any(run.status is RunStatus.FAIL for run in selected):
                state = "failed"
                detail = "The mapped customer scenario executed but its authoritative result failed."
            elif any(run.status in {RunStatus.BLOCKED, RunStatus.INCONCLUSIVE} for run in selected):
                state = "inconclusive"
                detail = "The mapped scenario was blocked or had an unknown result."
            else:
                state = "covered"
                detail = "The mapped customer scenario executed and produced deterministic evidence."
            result.append(CoverageResult(str(check["dimension"]), state, scenario_ids, evidence_ids, detail))
        mapped_capabilities = {
            str(value).strip().lower()
            for check in plan.completeness_checks
            for value in check.get("capabilities", ())
        }
        for capability in capabilities:
            if capability.lower() not in mapped_capabilities:
                result.append(CoverageResult(f"capability:{capability}", "missing", (), (), "Declared capability has no mapped test scenario."))
        return result

    async def _review(
        self,
        plan: CodexTestPlan,
        runs: list[TestRun],
        coverage: list[CoverageResult],
        capabilities: tuple[str, ...],
    ) -> CodexReview:
        run_data = tuple(run.to_dict() for run in runs)
        plan_data = plan.to_dict() | {"coverage": [item.to_dict() for item in coverage]}
        try:
            response = await self.reasoner.complete(
                build_review_messages(plan=plan_data, runs=run_data, capabilities=capabilities),
                response_schema=REVIEW_SCHEMA,
            )
            payload = response.json_object()
            findings = payload.get("findings")
            missing = payload.get("missing_coverage")
            if not isinstance(findings, list) or not isinstance(missing, list):
                raise ReasoningProviderError("Codex review shape is invalid")
            run_ids = {run.run_id for run in runs}
            known_evidence: set[str] = {
                evidence_id
                for run in runs
                for step in run.step_results
                for evidence_id in step.evidence_ids
            }
            known_evidence.update(
                finding_id
                for run in runs
                for finding_id in run.finding_ids
            )
            for record in self.ledger.records():
                if record.get("aggregate_id") not in run_ids:
                    continue
                item = record.get("payload", {})
                if isinstance(item, Mapping):
                    for key in ("evidence_id", "event_id", "finding_id"):
                        value = item.get(key)
                        if isinstance(value, str) and value:
                            known_evidence.add(value)
            normalized: list[dict[str, Any]] = []
            unscoped: list[str] = []
            for finding in findings:
                if not isinstance(finding, Mapping):
                    raise ReasoningProviderError("Codex review finding must be an object")
                raw_evidence_ids = finding.get("evidence_ids", ())
                if not isinstance(raw_evidence_ids, list):
                    raw_evidence_ids = []
                evidence_ids = tuple(value for value in raw_evidence_ids if isinstance(value, str))
                if not evidence_ids or not set(evidence_ids).issubset(known_evidence):
                    title = str(finding.get("title") or "untitled finding")
                    unscoped.append(f"Review finding {title!r} has no evidence entirely within the executed scope.")
                    continue
                normalized.append(dict(finding) | {"evidence_ids": list(evidence_ids), "source": "codex"})
            missing_items = tuple(
                [str(item) for item in missing if str(item).strip()]
                + unscoped
            )
            status = "pass" if not normalized and not missing_items else "findings"
            return CodexReview(status, str(payload.get("summary") or ""), tuple(normalized), missing_items, response.response_id)
        except Exception as exc:
            return CodexReview(
                "inconclusive",
                "Codex review did not settle; deterministic run and coverage results remain authoritative.",
                (),
                (),
                error=f"{type(exc).__name__}: {exc}",
            )

    @staticmethod
    def _coverage_limitations(coverage: list[CoverageResult]) -> tuple[str, ...]:
        return tuple(
            f"Coverage {item.dimension} is {item.status}: {item.detail}"
            for item in coverage
            if item.status != "covered"
        )

    @staticmethod
    def _settle_status(
        runs: list[TestRun],
        coverage: list[CoverageResult],
        review: CodexReview,
    ) -> str:
        if not runs:
            return "blocked"
        if any(run.status is RunStatus.FAIL for run in runs):
            return "fail"
        if any(run.status in {RunStatus.BLOCKED, RunStatus.INCONCLUSIVE} for run in runs):
            return "inconclusive"
        if any(item.status != "covered" for item in coverage):
            return "incomplete"
        if review.status == "inconclusive":
            return "inconclusive"
        if review.findings or review.missing_coverage:
            return "fail"
        return "pass"


def _schema_or_none(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if isinstance(value, str):
        decoded = _decode_jsonish(value, "profile schema")
        if decoded is None:
            return None
        value = decoded
    if not isinstance(value, Mapping):
        raise ReasoningProviderError("discovered schema must be an object")
    return dict(value)


def _decode_jsonish(value: Any, field: str) -> Any:
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except json.JSONDecodeError as exc:
        raise ReasoningProviderError(f"{field} must contain valid JSON") from exc


def _mapping_or_empty(value: Any, field: str) -> dict[str, Any]:
    decoded = _decode_jsonish(value, field)
    if decoded is None:
        return {}
    if not isinstance(decoded, Mapping):
        raise ReasoningProviderError(f"{field} must decode to an object")
    return dict(decoded)


def _contains_any(text: str, candidates: tuple[str, ...]) -> bool:
    return any(candidate in text for candidate in candidates)


def _contains_empty_value(value: Any) -> bool:
    if value is None or value == "" or value == {}:
        return True
    if isinstance(value, Mapping):
        return any(_contains_empty_value(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(_contains_empty_value(item) for item in value)
    return False
