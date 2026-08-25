"""Evidence-first Agent understanding and customer simulation testing.

The package is independent of any orchestration framework. Codex is an
optional reasoning/exploration boundary; adapters, runner, validators and the
ledger remain deterministic and can run without a model session.
"""

from .adapters import (
    AdapterDescription,
    AsyncJobAdapter,
    CallableAdapter,
    CliAdapter,
    HttpAdapter,
    SessionContext,
    UnderTestAdapter,
)
from .codex_tester import (
    DISCOVERY_PLAN_SCHEMA,
    MINIMUM_COVERAGE,
    REVIEW_SCHEMA,
    CodexCustomerTester,
    CodexReview,
    CodexTestPlan,
    CodexTestReport,
    CoverageResult as CodexCoverageResult,
    build_dimension_messages,
    build_discovery_messages,
    build_review_messages,
)
from .environment import FixtureEnvironment
from .evolution import EvolutionApproval, EvolutionCanaryMetrics, EvolutionGovernor, evaluate_evolution_canary
from .ledger import EvidenceLedger
from .models import (
    AgentContractProfile,
    ContractHypothesis,
    Correction,
    CustomerJourney,
    EvidenceLevel,
    EvidenceRef,
    EvolutionProposal,
    FactStatus,
    Finding,
    FindingKind,
    JourneyStep,
    RawObservation,
    RegressionPlan,
    RunStatus,
    Severity,
    StepResult,
    StepStatus,
    TestRun,
)
from .reasoning import (
    PROPOSAL_RESPONSE_SCHEMA,
    CodexReasoner,
    ReasoningProvider,
    ReasoningProviderError,
    ReasoningResponse,
    build_proposal_messages,
    proposal_from_response,
)
from .regression import CorrectionImpactAnalyzer
from .runner import CustomerSimulationRunner
from .understanding import UnderstandingEngine

__all__ = [
    "PROPOSAL_RESPONSE_SCHEMA",
    "AdapterDescription",
    "AgentContractProfile",
    "AsyncJobAdapter",
    "CallableAdapter",
    "CliAdapter",
    "CodexCoverageResult",
    "CodexCustomerTester",
    "CodexReasoner",
    "CodexReview",
    "CodexTestPlan",
    "CodexTestReport",
    "ContractHypothesis",
    "Correction",
    "CorrectionImpactAnalyzer",
    "CustomerJourney",
    "CustomerSimulationRunner",
    "DISCOVERY_PLAN_SCHEMA",
    "EvidenceLedger",
    "EvidenceLevel",
    "EvidenceRef",
    "EvolutionApproval",
    "EvolutionCanaryMetrics",
    "EvolutionGovernor",
    "EvolutionProposal",
    "FactStatus",
    "Finding",
    "FindingKind",
    "FixtureEnvironment",
    "HttpAdapter",
    "JourneyStep",
    "MINIMUM_COVERAGE",
    "RawObservation",
    "ReasoningProvider",
    "ReasoningProviderError",
    "ReasoningResponse",
    "RegressionPlan",
    "REVIEW_SCHEMA",
    "RunStatus",
    "SessionContext",
    "Severity",
    "StepResult",
    "StepStatus",
    "TestRun",
    "UnderTestAdapter",
    "UnderstandingEngine",
    "build_discovery_messages",
    "build_dimension_messages",
    "build_proposal_messages",
    "build_review_messages",
    "evaluate_evolution_canary",
    "proposal_from_response",
]
