"""Deterministic fixture and side-effect boundary for local scenarios."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .models import digest


@dataclass
class FixtureEnvironment:
    fixtures: dict[str, Any] = field(default_factory=dict)
    _initial: dict[str, Any] = field(default_factory=dict, init=False, repr=False)

    def register(self, name: str, value: Any) -> None:
        if not name.strip():
            raise ValueError("fixture name is required")
        self.fixtures[name] = value
        self._initial[name] = value

    def get(self, name: str) -> Any:
        if name not in self.fixtures:
            raise KeyError(name)
        return self.fixtures[name]

    def set_runtime(self, name: str, value: Any) -> None:
        if name not in self.fixtures:
            raise KeyError(name)
        self.fixtures[name] = value

    def reset(self) -> None:
        self.fixtures = dict(self._initial)

    def snapshot(self) -> dict[str, Any]:
        return {
            "fixture_names": sorted(self.fixtures),
            "fixture_digest": digest(self.fixtures),
        }
