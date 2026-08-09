"""Optional OpenAI-compatible reasoning boundary.

The provider is deliberately proposal-only.  It never writes a Profile,
changes a Journey, or settles a TestRun.
"""
from __future__ import annotations

import asyncio
import json
import os
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .models import EvolutionProposal


class ReasoningProviderError(RuntimeError):
    pass


_MANAGED_ENV_KEYS = frozenset(
    {
        "LLM_PROVIDER",
        "LLM_API_KEY",
        "LLM_BASE_URL",
        "LLM_MODEL",
        "OPENAI_API_KEY",
        "OPENAI_BASE_URL",
        "OPENAI_MODEL",
        "AAWO_TESTER_LLM_API_KEY",
        "AAWO_TESTER_LLM_BASE_URL",
        "AAWO_TESTER_LLM_MODEL",
    }
)


def load_managed_env(path: str | os.PathLike[str] = ".env.local") -> tuple[str, ...]:
    """Load only LLM variables from the skill-managed local env file.

    The file is treated as a local secret source. Values are placed in the
    process environment and are never returned or logged; existing process
    variables always win. Production callers should inject environment
    variables through their secret manager and skip this helper.
    """
    env_path = Path(path)
    if not env_path.is_file():
        return ()
    loaded: list[str] = []
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key not in _MANAGED_ENV_KEYS or key in os.environ:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ[key] = value
        loaded.append(key)
    return tuple(loaded)


def _first_env(*names: str) -> str:
    for name in names:
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return ""


PROPOSAL_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["kind", "base_revision", "proposed_change", "evidence_ids"],
    "properties": {
        "kind": {"type": "string", "enum": ["contract", "scenario", "evaluator", "workflow", "team"]},
        "base_revision": {"type": "integer"},
        "proposed_change": {"type": "object"},
        "evidence_ids": {"type": "array", "items": {"type": "string"}},
        "risk": {"type": "string", "enum": ["low", "normal", "high", "critical"]},
    },
}


def build_proposal_messages(
    *,
    agent_id: str,
    kind: str,
    base_revision: int,
    contract: dict[str, Any],
    journey: dict[str, Any],
    evidence: tuple[dict[str, Any], ...],
    correction: str | None = None,
) -> tuple[dict[str, str], ...]:
    """Build a bounded, auditable prompt for proposal-only reasoning."""
    if kind not in {"contract", "scenario", "evaluator", "workflow", "team"}:
        raise ValueError("unsupported proposal kind")
    context = {
        "agent_id": agent_id,
        "target_kind": kind,
        "base_revision": base_revision,
        "contract": contract,
        "customer_journey": journey,
        "evidence": list(evidence),
        "user_correction": correction or "",
    }
    system = (
        "You are a governed Agent quality analyst. Understand the supplied Agent contract, "
        "customer journey, evidence, and user correction. Produce exactly one JSON object "
        "with kind, base_revision, proposed_change, evidence_ids, and risk. Choose only the "
        f"requested kind ({kind!r}); use only evidence IDs present in the input; never claim "
        "a test passed, never invent evidence, and never apply the change. If evidence is "
        "insufficient, express a conservative proposal or fail with no JSON. Do not use Markdown."
    )
    user = json.dumps(context, ensure_ascii=False, sort_keys=True)
    return ({"role": "system", "content": system}, {"role": "user", "content": user})


@dataclass(frozen=True)
class ReasoningResponse:
    response_id: str
    model: str
    content: str
    raw_metadata: dict[str, Any]

    def json_object(self) -> dict[str, Any]:
        try:
            value = json.loads(self.content)
        except json.JSONDecodeError as exc:
            raise ReasoningProviderError("reasoning response is not valid JSON") from exc
        if not isinstance(value, dict):
            raise ReasoningProviderError("reasoning response must be a JSON object")
        return value


class ReasoningProvider(Protocol):
    async def complete(
        self,
        messages: tuple[dict[str, str], ...],
        *,
        response_schema: dict[str, Any] | None = None,
    ) -> ReasoningResponse: ...

    async def propose_evolution(
        self,
        *,
        agent_id: str,
        kind: str,
        base_revision: int,
        contract: dict[str, Any],
        journey: dict[str, Any],
        evidence: tuple[dict[str, Any], ...],
        correction: str | None = None,
    ) -> EvolutionProposal: ...


class OpenAICompatibleReasoner:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        model: str | None = None,
        api_key: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.base_url = (
            base_url
            or _first_env("AAWO_TESTER_LLM_BASE_URL", "LLM_BASE_URL", "OPENAI_BASE_URL")
        ).rstrip("/")
        self.model = model or _first_env("AAWO_TESTER_LLM_MODEL", "LLM_MODEL", "OPENAI_MODEL")
        self.api_key = api_key or _first_env("AAWO_TESTER_LLM_API_KEY", "LLM_API_KEY", "OPENAI_API_KEY")
        self.timeout = timeout
        if not self.base_url or not self.model or not self.api_key:
            raise ValueError("base_url, model and api_key are required; credentials are read process-only")

    async def complete(
        self,
        messages: tuple[dict[str, str], ...],
        *,
        response_schema: dict[str, Any] | None = None,
    ) -> ReasoningResponse:
        return await asyncio.to_thread(self._complete_sync, messages, response_schema)

    async def propose_evolution(
        self,
        *,
        agent_id: str,
        kind: str,
        base_revision: int,
        contract: dict[str, Any],
        journey: dict[str, Any],
        evidence: tuple[dict[str, Any], ...],
        correction: str | None = None,
    ) -> EvolutionProposal:
        """Ask the real model for a proposal while keeping application authority local."""
        messages = build_proposal_messages(
            agent_id=agent_id,
            kind=kind,
            base_revision=base_revision,
            contract=contract,
            journey=journey,
            evidence=evidence,
            correction=correction,
        )
        last_error: ReasoningProviderError | None = None
        for attempt in range(2):
            response = await self.complete(messages, response_schema=PROPOSAL_RESPONSE_SCHEMA)
            try:
                proposal = proposal_from_response(response)
                evidence_ids = {item.get("evidence_id") for item in evidence if isinstance(item, dict)}
                if proposal.kind != kind:
                    raise ReasoningProviderError("model proposal kind does not match requested kind")
                if proposal.base_revision != base_revision:
                    raise ReasoningProviderError("model proposal base revision is stale or mismatched")
                if not set(proposal.evidence_ids).issubset(evidence_ids):
                    raise ReasoningProviderError("model proposal references evidence outside the supplied scope")
                return proposal
            except ReasoningProviderError as exc:
                last_error = exc
                if attempt == 0:
                    messages = messages + (
                        {
                            "role": "user",
                            "content": (
                                "Deterministic validation rejected the previous response. Retry once. "
                                "Return one JSON object only: proposed_change MUST be a JSON object, "
                                "not prose or a JSON-encoded string; use only the supplied evidence IDs."
                            ),
                        },
                    )
        assert last_error is not None
        raise last_error

    def _complete_sync(
        self,
        messages: tuple[dict[str, str], ...],
        response_schema: dict[str, Any] | None,
    ) -> ReasoningResponse:
        url = self.base_url if self.base_url.endswith("/chat/completions") else f"{self.base_url}/chat/completions"
        payload: dict[str, Any] = {"model": self.model, "messages": list(messages), "temperature": 0}
        if response_schema is not None:
            payload["response_format"] = {"type": "json_object"}
        request = Request(
            url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                body = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise ReasoningProviderError(f"reasoning HTTP {exc.code}") from exc
        except (URLError, TimeoutError, OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ReasoningProviderError(f"reasoning transport failure: {type(exc).__name__}") from exc
        try:
            choice = body["choices"][0]
            content = choice["message"]["content"]
            if not isinstance(content, str):
                raise TypeError("message content is not text")
        except (KeyError, IndexError, TypeError) as exc:
            raise ReasoningProviderError("reasoning response violates chat completion shape") from exc
        return ReasoningResponse(
            response_id=str(body.get("id") or uuid.uuid4().hex),
            model=str(body.get("model") or self.model),
            content=content,
            raw_metadata={"usage": body.get("usage", {}), "provider_model": body.get("model")},
        )


def proposal_from_response(
    response: ReasoningResponse,
    *,
    proposal_id: str | None = None,
) -> EvolutionProposal:
    payload = response.json_object()
    required = {"kind", "base_revision", "proposed_change", "evidence_ids"}
    missing = sorted(required - set(payload))
    if missing:
        raise ReasoningProviderError(f"proposal missing required fields: {', '.join(missing)}")
    evidence_ids = payload["evidence_ids"]
    if not isinstance(evidence_ids, list) or not evidence_ids or not all(isinstance(item, str) and item.strip() for item in evidence_ids):
        raise ReasoningProviderError("proposal evidence_ids must be a non-empty string list")
    change = payload["proposed_change"]
    if isinstance(change, str):
        try:
            change = json.loads(change)
        except json.JSONDecodeError as exc:
            raise ReasoningProviderError("proposal proposed_change string is not JSON") from exc
    if not isinstance(change, dict):
        raise ReasoningProviderError("proposal proposed_change must be an object")
    try:
        return EvolutionProposal(
            proposal_id=proposal_id or f"proposal_{uuid.uuid4().hex}",
            kind=str(payload["kind"]),
            base_revision=int(payload["base_revision"]),
            proposed_change=change,
            evidence_ids=tuple(evidence_ids),
            risk=str(payload.get("risk") or "normal"),
        )
    except (TypeError, ValueError) as exc:
        raise ReasoningProviderError("proposal fields violate the governed EvolutionProposal contract") from exc
