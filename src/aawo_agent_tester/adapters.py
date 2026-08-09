"""Explicit adapters for black-box Agent interaction."""
from __future__ import annotations

import asyncio
import inspect
import json
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .models import RawObservation


@dataclass(frozen=True)
class AdapterDescription:
    adapter_id: str
    channel: str
    side_effect_policy: str = "read_only"
    capabilities: tuple[str, ...] = ()


@dataclass(frozen=True)
class SessionContext:
    run_id: str
    actor: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


class UnderTestAdapter(Protocol):
    def describe(self) -> AdapterDescription: ...
    async def open_session(self, context: SessionContext) -> Any: ...
    async def send(self, session: Any, payload: Any) -> RawObservation: ...
    async def observe(self, session: Any) -> tuple[RawObservation, ...]: ...
    async def reset(self, session: Any) -> None: ...
    async def close(self, session: Any) -> None: ...


class CallableAdapter:
    def __init__(self, adapter_id: str, function: Callable[..., Any], *, side_effect_policy: str = "read_only") -> None:
        self._description = AdapterDescription(adapter_id, "callable", side_effect_policy, ("send",))
        self._function = function

    def describe(self) -> AdapterDescription:
        return self._description

    async def open_session(self, context: SessionContext) -> dict[str, Any]:
        return {"context": context, "last": None}

    async def send(self, session: dict[str, Any], payload: Any) -> RawObservation:
        try:
            if len(inspect.signature(self._function).parameters) >= 2:
                result = self._function(payload, session["context"])
            else:
                result = self._function(payload)
            if inspect.isawaitable(result):
                result = await result
            observation = result if isinstance(result, RawObservation) else RawObservation(output=result)
            session["last"] = observation
            return observation
        except Exception as exc:  # adapter boundary must expose failure, not hide it
            observation = RawObservation(status="failed", error=f"{type(exc).__name__}: {exc}")
            session["last"] = observation
            return observation

    async def observe(self, session: dict[str, Any]) -> tuple[RawObservation, ...]:
        return (session["last"],) if session.get("last") is not None else ()

    async def reset(self, session: dict[str, Any]) -> None:
        session["last"] = None

    async def close(self, session: dict[str, Any]) -> None:
        session.clear()


class HttpAdapter:
    def __init__(
        self,
        adapter_id: str,
        url: str,
        *,
        method: str = "POST",
        headers: dict[str, str] | None = None,
        timeout: float = 15.0,
    ) -> None:
        normalized_method = method.upper()
        if normalized_method not in {"GET", "POST"}:
            raise ValueError("HTTP adapter currently supports GET and POST")
        self._description = AdapterDescription(adapter_id, "http", "read_only", ("send", normalized_method.lower()))
        self.url = url
        self.method = normalized_method
        self.headers = dict(headers or {})
        self.timeout = timeout

    def describe(self) -> AdapterDescription:
        return self._description

    async def open_session(self, context: SessionContext) -> dict[str, Any]:
        return {"context": context, "last": None}

    async def send(self, session: dict[str, Any], payload: Any) -> RawObservation:
        def request() -> RawObservation:
            body = None if self.method == "GET" else json.dumps(payload, ensure_ascii=False).encode("utf-8")
            request_obj = Request(
                self.url,
                data=body,
                headers={"Content-Type": "application/json", **self.headers},
                method=self.method,
            )
            try:
                with urlopen(request_obj, timeout=self.timeout) as response:
                    raw = response.read()
                    try:
                        output: Any = json.loads(raw.decode("utf-8"))
                    except (UnicodeDecodeError, json.JSONDecodeError):
                        output = raw.decode("utf-8", errors="replace")
                    return RawObservation(output=output, metadata={"status_code": response.status})
            except HTTPError as exc:
                return RawObservation(status="failed", error=f"HTTP {exc.code}: {exc.reason}", metadata={"status_code": exc.code})
            except (URLError, TimeoutError, OSError) as exc:
                return RawObservation(status="unknown", error=f"transport: {exc}")

        observation = await asyncio.to_thread(request)
        session["last"] = observation
        return observation

    async def observe(self, session: dict[str, Any]) -> tuple[RawObservation, ...]:
        return (session["last"],) if session.get("last") is not None else ()

    async def reset(self, session: dict[str, Any]) -> None:
        session["last"] = None

    async def close(self, session: dict[str, Any]) -> None:
        session.clear()


class CliAdapter:
    def __init__(self, adapter_id: str, executable: str, args: tuple[str, ...] = ()) -> None:
        self._description = AdapterDescription(adapter_id, "cli", "read_only", ("send",))
        self.executable = executable
        self.args = args

    def describe(self) -> AdapterDescription:
        return self._description

    async def open_session(self, context: SessionContext) -> dict[str, Any]:
        return {"context": context, "last": None}

    async def send(self, session: dict[str, Any], payload: Any) -> RawObservation:
        command = (self.executable, *self.args)
        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdin = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            stdout, stderr = await process.communicate(stdin)
            if process.returncode != 0:
                observation = RawObservation(status="failed", error=stderr.decode("utf-8", errors="replace"), metadata={"returncode": process.returncode})
            else:
                text = stdout.decode("utf-8", errors="replace")
                try:
                    output: Any = json.loads(text)
                except json.JSONDecodeError:
                    output = text
                observation = RawObservation(output=output, metadata={"returncode": 0})
        except (OSError, ValueError) as exc:
            observation = RawObservation(status="failed", error=f"cli: {exc}")
        session["last"] = observation
        return observation

    async def observe(self, session: dict[str, Any]) -> tuple[RawObservation, ...]:
        return (session["last"],) if session.get("last") is not None else ()

    async def reset(self, session: dict[str, Any]) -> None:
        session["last"] = None

    async def close(self, session: dict[str, Any]) -> None:
        session.clear()


class AsyncJobAdapter:
    """Adapter for submit/poll Agent APIs.

    Reaching the poll bound returns ``unknown`` and never cancels the remote
    job implicitly.  The caller must reconcile that result explicitly.
    """

    def __init__(
        self,
        adapter_id: str,
        submit: Callable[[Any], str | Awaitable[str]],
        poll: Callable[[str], RawObservation | Awaitable[RawObservation]],
        *,
        poll_interval: float = 0.01,
        max_polls: int = 20,
        side_effect_policy: str = "read_only",
    ) -> None:
        if max_polls < 1 or poll_interval < 0:
            raise ValueError("async job polling bounds must be positive")
        self._description = AdapterDescription(adapter_id, "async_job", side_effect_policy, ("send", "poll"))
        self._submit = submit
        self._poll = poll
        self._poll_interval = poll_interval
        self._max_polls = max_polls

    def describe(self) -> AdapterDescription:
        return self._description

    async def open_session(self, context: SessionContext) -> dict[str, Any]:
        return {"context": context, "last": None, "job_id": None}

    async def send(self, session: dict[str, Any], payload: Any) -> RawObservation:
        try:
            job_id = self._submit(payload)
            if inspect.isawaitable(job_id):
                job_id = await job_id
            job_id = str(job_id)
            session["job_id"] = job_id
            for _ in range(self._max_polls):
                observation = self._poll(job_id)
                if inspect.isawaitable(observation):
                    observation = await observation
                if not isinstance(observation, RawObservation):
                    raise TypeError("async job poll must return RawObservation")
                if observation.status not in {"pending", "running"}:
                    session["last"] = observation
                    return observation
                if self._poll_interval:
                    await asyncio.sleep(self._poll_interval)
            observation = RawObservation(
                status="unknown",
                error="async job polling bound reached; remote job was not cancelled",
                metadata={"job_id": job_id, "max_polls": self._max_polls},
            )
        except Exception as exc:
            observation = RawObservation(status="failed", error=f"{type(exc).__name__}: {exc}")
        session["last"] = observation
        return observation

    async def observe(self, session: dict[str, Any]) -> tuple[RawObservation, ...]:
        return (session["last"],) if session.get("last") is not None else ()

    async def reset(self, session: dict[str, Any]) -> None:
        session["last"] = None
        session["job_id"] = None

    async def close(self, session: dict[str, Any]) -> None:
        session.clear()
