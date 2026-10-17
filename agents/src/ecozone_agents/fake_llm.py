"""Scripted fakes for tests: a `ModelClient` and a `Proposer`.

The `ModelClient`: answers are queued per role, so no test touches a network.

Each answer is a pydantic model (or a plain dict validated against the schema), an exception to
raise, or a function of the prompt. When a role's queue runs out the last answer repeats, which
keeps "the model keeps saying the same thing" tests short.
"""

import asyncio
import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel

from .errors import ModelError
from .ports import ModelOut, Proposal, ProposalRequest, Role

Answer = BaseModel | Mapping[str, Any] | Exception | Callable[[dict[str, object]], BaseModel | Mapping[str, Any]]


@dataclass
class Call:
    role: Role
    system: str
    prompt: str

    @property
    def json(self) -> dict[str, object]:
        return json.loads(self.prompt)


@dataclass
class ScriptedModel:
    proposer: Sequence[Answer] = ()
    writer: Sequence[Answer] = ()
    delay_s: dict[Role, float] = field(default_factory=dict[Role, float])
    calls: list[Call] = field(default_factory=list[Call])
    _used: dict[Role, int] = field(default_factory=lambda: {"proposer": 0, "writer": 0})

    async def generate(self, *, role: Role, system: str, prompt: str, schema: type[ModelOut]) -> ModelOut:
        self.calls.append(Call(role, system, prompt))
        if self.delay_s.get(role):
            await asyncio.sleep(self.delay_s[role])
        script = self.proposer if role == "proposer" else self.writer
        if not script:
            raise ModelError(f"No scripted answer for the {role}.")
        answer = script[min(self._used[role], len(script) - 1)]
        self._used[role] += 1
        if isinstance(answer, Exception):
            raise answer
        if callable(answer):
            answer = answer(json.loads(prompt))
        try:
            return schema.model_validate(answer.model_dump() if isinstance(answer, BaseModel) else answer)
        except ValueError as exc:
            raise ModelError("The scripted answer does not match the schema.") from exc

    def count(self, role: Role) -> int:
        return sum(1 for call in self.calls if call.role == role)


@dataclass
class ScriptedProposer:
    """Returns the queued proposals per round (the last list repeats) and records what it was shown."""

    rounds: Sequence[Sequence[Proposal]] = ()
    error: Exception | None = None
    delay_s: float = 0.0
    requests: list[ProposalRequest] = field(default_factory=list[ProposalRequest])

    async def propose(self, request: ProposalRequest) -> list[Proposal]:
        self.requests.append(request)
        if self.delay_s:
            await asyncio.sleep(self.delay_s)
        if self.error:
            raise self.error
        if not self.rounds:
            return []
        return list(self.rounds[min(len(self.requests) - 1, len(self.rounds) - 1)])
