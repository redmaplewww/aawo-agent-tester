"""Codex SDK reasoning boundary for the customer-simulation tester.

The Codex thread is used only to understand an unfamiliar Agent, propose a
test contract/journey, and review evidence.  The deterministic runner remains
the authority for execution and settlement: a model response can never turn
a failed, blocked, or unknown observation into a pass.
"""
from __future__ import annotations

import asyncio
import json
import threading
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Protocol

from .models import EvolutionProposal


class ReasoningProviderError(RuntimeError):
    """Raised when the Codex SDK cannot produce a governed response."""


PROPOSAL_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["kind", "base_revision", "proposed_change_json", "evidence_ids", "risk"],
    "properties": {
        "kind": {"type": "string", "enum": ["contract", "scenario", "evaluator", "workflow", "team"]},
        "base_revision": {"type": "integer"},
        "proposed_change_json": {"type": "string"},
        "evidence_ids": {"type": "array", "items": {"type": "string"}},
        "risk": {"type": "string", "enum": ["low", "normal", "high", "critical"]},
    },
    "additionalProperties": False,
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
    """Build a bounded prompt understood by Codex, not a chat-completions payload."""
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
        "You are the evidence-governed quality analyst for an unfamiliar Agent. "
        "Understand the supplied contract, customer journey, evidence, and user correction. "
        "Return exactly one JSON object matching the supplied output schema. "
        f"The requested proposal kind is {kind!r}. Use only evidence IDs present in the input. "
        "Encode the arbitrary proposed change in proposed_change_json as a JSON string. "
        "Never claim that a test passed, never invent evidence, never apply a change, and "
        "never silently repair a failed observation. If evidence is insufficient, make a "
        "conservative proposal or report the uncertainty in the proposed change."
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
            raise ReasoningProviderError("Codex response is not valid JSON") from exc
        if not isinstance(value, dict):
            raise ReasoningProviderError("Codex response must be a JSON object")
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


def _plain(value: Any) -> Any:
    """Convert SDK/Pydantic values to JSON-safe metadata without secrets."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        try:
            return _plain(model_dump())
        except Exception:
            return {"type": type(value).__name__}
    return {"type": type(value).__name__}


class CodexReasoner:
    """Use one read-only Codex thread for bounded understanding proposals.

    ``openai-codex`` reuses the local Codex account/session.  No API key is
    accepted by this class and no provider URL is constructed.  The client is
    created lazily so deterministic tests and offline runs do not start a
    Codex process unless a reasoning call is requested.  Every turn has a
    bounded timeout; timeout is reported as blocked/inconclusive by callers.
    """

    model = "codex"
    supports_dimension_planning = True

    def __init__(
        self,
        *,
        model: str | None = None,
        cwd: str | Path | None = None,
        client_factory: Callable[[], Any] | None = None,
        turn_timeout: float = 90.0,
    ) -> None:
        if turn_timeout <= 0:
            raise ValueError("turn_timeout must be positive")
        self.model = model or "codex"
        self.cwd = str(Path(cwd).resolve()) if cwd is not None else None
        self._client_factory = client_factory
        self.turn_timeout = turn_timeout
        self._codex: Any | None = None
        self._thread: Any | None = None
        self._lock = threading.RLock()

    async def complete(
        self,
        messages: tuple[dict[str, str], ...],
        *,
        response_schema: dict[str, Any] | None = None,
    ) -> ReasoningResponse:
        loop = asyncio.get_running_loop()
        result_future: asyncio.Future[ReasoningResponse] = loop.create_future()

        def deliver_result(value: ReasoningResponse) -> None:
            if not result_future.done():
                result_future.set_result(value)

        def deliver_error(error: BaseException) -> None:
            if not result_future.done():
                result_future.set_exception(error)

        def schedule(callback: Callable[..., None], *args: Any) -> None:
            try:
                loop.call_soon_threadsafe(callback, *args)
            except RuntimeError:
                # The caller timed out and closed its event loop while the
                # daemon SDK worker was still unwinding.
                return

        def worker() -> None:
            try:
                value = self._complete_sync(messages, response_schema)
            except BaseException as exc:  # deliver SDK failures without hiding cancellation
                schedule(deliver_error, exc)
            else:
                schedule(deliver_result, value)

        threading.Thread(
            target=worker,
            name="codex-agent-tester-turn",
            daemon=True,
        ).start()
        try:
            return await asyncio.wait_for(result_future, timeout=self.turn_timeout)
        except asyncio.TimeoutError as exc:
            # The SDK call is synchronous.  Closing in another daemon thread
            # prevents a stuck CLI child from keeping the tester process alive.
            threading.Thread(target=self.close, name="codex-agent-tester-close", daemon=True).start()
            raise ReasoningProviderError(
                f"Codex turn timed out after {self.turn_timeout:g}s"
            ) from exc

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
        messages = build_proposal_messages(
            agent_id=agent_id,
            kind=kind,
            base_revision=base_revision,
            contract=contract,
            journey=journey,
            evidence=evidence,
            correction=correction,
        )
        allowed_evidence = {
            item.get("evidence_id") for item in evidence if isinstance(item, dict)
        }
        last_error: ReasoningProviderError | None = None
        for attempt in range(2):
            response = await self.complete(messages, response_schema=PROPOSAL_RESPONSE_SCHEMA)
            try:
                proposal = proposal_from_response(response)
                if proposal.kind != kind:
                    raise ReasoningProviderError("Codex proposal kind does not match the request")
                if proposal.base_revision != base_revision:
                    raise ReasoningProviderError("Codex proposal base revision is stale or mismatched")
                if not set(proposal.evidence_ids).issubset(allowed_evidence):
                    raise ReasoningProviderError(
                        "Codex proposal references evidence outside the supplied scope"
                    )
                return proposal
            except ReasoningProviderError as exc:
                last_error = exc
                if attempt == 0:
                    messages = messages + (
                        {
                            "role": "user",
                            "content": (
                                "Deterministic validation rejected the previous response. Retry once. "
                                "Return one JSON object only; proposed_change_json must be a JSON-encoded "
                                "object, and evidence_ids may use only supplied IDs."
                            ),
                        },
                    )
        assert last_error is not None
        raise last_error

    def close(self) -> None:
        with self._lock:
            codex = self._codex
            self._thread = None
            self._codex = None
        close = getattr(codex, "close", None) if codex is not None else None
        if callable(close):
            # A stuck SDK turn must not make application shutdown hang.  The
            # bundled CLI owns its child process; close it asynchronously after
            # detaching it from this reasoner.
            threading.Thread(target=close, name="codex-agent-tester-sdk-close", daemon=True).start()

    def _ensure_thread(self) -> Any:
        with self._lock:
            if self._thread is not None:
                return self._thread
            try:
                if self._client_factory is not None:
                    self._codex = self._client_factory()
                else:
                    from openai_codex import Codex

                    self._codex = Codex()
                from openai_codex import ApprovalMode, Sandbox

                self._thread = self._codex.thread_start(
                    approval_mode=ApprovalMode.deny_all,
                    sandbox=Sandbox.read_only,
                    cwd=self.cwd,
                    ephemeral=True,
                    model=None if self.model == "codex" else self.model,
                    base_instructions=(
                        "You are a read-only quality analyst. Do not edit files, run destructive commands, "
                        "change the target Agent, or claim that an unexecuted test passed. Return only the "
                        "requested JSON object when an output schema is supplied."
                    ),
                )
                return self._thread
            except Exception as exc:
                self.close()
                raise ReasoningProviderError(
                    f"Codex SDK unavailable: {type(exc).__name__}"
                ) from exc

    def _complete_sync(
        self,
        messages: tuple[dict[str, str], ...],
        response_schema: dict[str, Any] | None,
    ) -> ReasoningResponse:
        prompt = "\n\n".join(
            f"[{message.get('role', 'user').upper()}]\n{message.get('content', '')}"
            for message in messages
        )
        with self._lock:
            thread = self._ensure_thread()
        try:
            result = thread.run(prompt, output_schema=response_schema)
        except Exception as exc:
            raise ReasoningProviderError(
                f"Codex turn failed: {type(exc).__name__}"
            ) from exc
        final_response = getattr(result, "final_response", None)
        if not isinstance(final_response, str) or not final_response.strip():
            status = getattr(result, "status", "unknown")
            raise ReasoningProviderError(f"Codex turn returned no final response (status={status})")
        usage = _plain(getattr(result, "usage", None))
        return ReasoningResponse(
            response_id=str(getattr(result, "id", None) or uuid.uuid4().hex),
            model=self.model,
            content=final_response,
            raw_metadata={"status": str(getattr(result, "status", "unknown")), "usage": usage},
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
    if (
        not isinstance(evidence_ids, list)
        or not evidence_ids
        or not all(isinstance(item, str) and item.strip() for item in evidence_ids)
    ):
        raise ReasoningProviderError("proposal evidence_ids must be a non-empty string list")
    change = payload.get("proposed_change")
    if change is None and "proposed_change_json" in payload:
        encoded_change = payload["proposed_change_json"]
        if not isinstance(encoded_change, str):
            raise ReasoningProviderError("proposal proposed_change_json must be a string")
        try:
            change = json.loads(encoded_change)
        except json.JSONDecodeError as exc:
            raise ReasoningProviderError("proposal proposed_change_json is not valid JSON") from exc
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
        raise ReasoningProviderError(
            "proposal fields violate the governed EvolutionProposal contract"
        ) from exc
