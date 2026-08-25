"""Evidence-aware profile induction and user correction handling."""
from __future__ import annotations

from dataclasses import replace
from typing import Any
import uuid

from .ledger import EvidenceLedger
from .models import (
    AgentContractProfile,
    ContractHypothesis,
    Correction,
    EvidenceLevel,
    EvidenceRef,
    FactStatus,
    digest,
)
from .schema import infer_schema


class UnderstandingEngine:
    def __init__(self, ledger: EvidenceLedger) -> None:
        self.ledger = ledger

    def create_profile(
        self,
        agent_id: str,
        adapter_id: str,
        *,
        purpose: str = "",
        input_schema: dict[str, Any] | None = None,
        output_schema: dict[str, Any] | None = None,
        source: str = "operator",
    ) -> AgentContractProfile:
        profile = AgentContractProfile(agent_id, adapter_id, purpose, input_schema=input_schema, output_schema=output_schema)
        hypotheses: list[ContractHypothesis] = []
        if input_schema is not None:
            hypotheses.append(self._record_hypothesis(profile, "input_schema", input_schema, FactStatus.DECLARED, EvidenceLevel.E1, source))
        if output_schema is not None:
            hypotheses.append(self._record_hypothesis(profile, "output_schema", output_schema, FactStatus.DECLARED, EvidenceLevel.E1, source))
        if hypotheses:
            profile = replace(
                profile,
                hypotheses=tuple(hypotheses),
                evidence_ids=tuple(item.evidence_ids[0] for item in hypotheses),
            )
        self.ledger.append(f"profile_{agent_id}_v1", "profile.created", agent_id, profile.to_dict())
        return profile

    def observe_output(self, profile: AgentContractProfile, output: Any, *, source: str = "test_run") -> AgentContractProfile:
        evidence_id = f"evidence_{uuid.uuid4().hex}"
        evidence = EvidenceRef(evidence_id, source, EvidenceLevel.E2, "observed output schema", digest(output))
        self.ledger.append(evidence_id, "evidence.observed", profile.agent_id, evidence.to_dict() | {"output": output})
        schema = infer_schema(output)
        hypothesis = ContractHypothesis("output_schema", schema, FactStatus.OBSERVED, EvidenceLevel.E2, (evidence_id,), profile.revision + 1)
        updated = profile.with_hypothesis(hypothesis)
        self.ledger.append(f"profile_{profile.agent_id}_v{updated.revision}", "profile.revised", profile.agent_id, updated.to_dict())
        return updated

    def apply_correction(self, profile: AgentContractProfile, correction: Correction) -> AgentContractProfile:
        self.ledger.append(correction.correction_id, "correction.created", profile.agent_id, correction.to_dict())
        old = next((item for item in profile.hypotheses if item.path == correction.target and item.status is not FactStatus.SUPERSEDED), None)
        retained = tuple(
            replace(item, status=FactStatus.SUPERSEDED)
            if item.path == correction.target and item.status is not FactStatus.SUPERSEDED
            else item
            for item in profile.hypotheses
        )
        if old is not None:
            retained = tuple(replace(item, status=FactStatus.SUPERSEDED) if item is old else item for item in retained)
        hypothesis = ContractHypothesis(correction.target, correction.corrected_fact, FactStatus.CONFIRMED, EvidenceLevel.E4, correction.evidence_ids, profile.revision + 1)
        field_updates: dict[str, Any] = {}
        if correction.target in {"input_schema", "output_schema", "error_schema"}:
            if not isinstance(correction.corrected_fact, dict):
                raise TypeError(f"{correction.target} correction must be an object schema")
            field_updates[correction.target] = dict(correction.corrected_fact)
        updated = replace(
            profile,
            revision=profile.revision + 1,
            hypotheses=retained + (hypothesis,),
            evidence_ids=tuple(dict.fromkeys(profile.evidence_ids + correction.evidence_ids)),
            **field_updates,
        )
        self.ledger.append(f"profile_{profile.agent_id}_v{updated.revision}", "profile.corrected", profile.agent_id, updated.to_dict())
        return updated

    def load_profile(self, agent_id: str) -> AgentContractProfile:
        records = tuple(
            record
            for record in self.ledger.records(aggregate_id=agent_id)
            if record["record_type"] in {"profile.created", "profile.revised", "profile.corrected"}
        )
        if not records:
            raise KeyError(agent_id)
        return AgentContractProfile.from_dict(records[-1]["payload"])

    def _record_hypothesis(self, profile: AgentContractProfile, path: str, value: Any, status: FactStatus, level: EvidenceLevel, source: str) -> ContractHypothesis:
        evidence_id = f"evidence_{uuid.uuid4().hex}"
        evidence = EvidenceRef(evidence_id, source, level, f"declared {path}", digest(value))
        self.ledger.append(evidence_id, "evidence.declared", profile.agent_id, evidence.to_dict() | {"value": value})
        return ContractHypothesis(path, value, status, level, (evidence_id,), profile.revision)
