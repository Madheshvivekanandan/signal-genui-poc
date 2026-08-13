"""A stand-in for the OpenAI client, built to the surface `agent` actually uses.

This is the one fake in the suite, and it sits at the only boundary this service
does not own. It is deliberately a fake rather than a `MagicMock`: it replays a
scripted sequence of partial-parse snapshots, so the test exercises the real
optimistic-emit loop -- "a molecule is only provably finished once the next one
has started" -- instead of asserting that a mock was called.

The scripted snapshots are the shape the SDK documents for
`beta.chat.completions.stream`: `content.delta` events carrying the object parsed
so far, then a final completion. If that contract changes, these tests are
supposed to break.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from types import TracebackType
from typing import Any, Self

from app.schemas import InspectAnswer, Molecule, SectionPlan


@dataclass(frozen=True, slots=True)
class Delta:
    """One `content.delta` event: the object as parsed up to this point."""

    parsed: dict[str, Any]
    type: str = "content.delta"


@dataclass(frozen=True, slots=True)
class Usage:
    prompt_tokens: int = 1200
    completion_tokens: int = 300
    total_tokens: int = 1500


# A module-level singleton, so it is not constructed in an argument default.
DEFAULT_USAGE = Usage()


@dataclass(frozen=True, slots=True)
class Message:
    # Either structured output the agent asks for: a section plan when streaming,
    # an inspect answer when parsing a review-pane question.
    parsed: SectionPlan | InspectAnswer | None
    refusal: str | None = None


@dataclass(frozen=True, slots=True)
class Choice:
    message: Message


@dataclass(frozen=True, slots=True)
class Completion:
    choices: list[Choice]
    usage: Usage | None = DEFAULT_USAGE


class FakeStream:
    """The context manager `beta.chat.completions.stream` returns."""

    def __init__(self, deltas: list[Delta], completion: Completion) -> None:
        self._deltas = deltas
        self._completion = completion

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None

    def __iter__(self) -> Iterator[Delta]:
        return iter(self._deltas)

    def get_final_completion(self) -> Completion:
        return self._completion


@dataclass
class FakeCompletions:
    """`client.beta.chat.completions`, with the two calls the agent makes."""

    deltas: list[Delta] = field(default_factory=list)
    completion: Completion | None = None
    parse_result: Any = None
    parse_error: Exception | None = None
    calls: list[dict[str, Any]] = field(default_factory=list)

    def stream(self, **kwargs: Any) -> FakeStream:
        self.calls.append(kwargs)
        assert self.completion is not None, "the test did not script a final completion"
        return FakeStream(self.deltas, self.completion)

    def parse(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if self.parse_error is not None:
            raise self.parse_error
        return self.parse_result


@dataclass
class FakeClient:
    """Just enough of `OpenAI` to stand in for it: `.beta.chat.completions`."""

    completions: FakeCompletions

    @property
    def beta(self) -> Self:
        return self

    @property
    def chat(self) -> Self:
        return self


def snapshots(molecules: list[Molecule], summary: str = "A read of the document.") -> list[Delta]:
    """Deltas that reveal `molecules` one at a time, as a real stream would.

    The last delta holds the complete list. The agent still declines to emit its
    final entry optimistically -- there is no following molecule to prove it
    finished -- and leaves it to the authoritative pass.
    """
    dumped = [molecule.model_dump(mode="json") for molecule in molecules]
    return [
        Delta({"summary": summary, "molecules": dumped[: index + 1]})
        for index in range(len(dumped))
    ]


def client_for(
    molecules: list[Molecule],
    *,
    summary: str = "A read of the document.",
    refusal: str | None = None,
    usage: Usage | None = DEFAULT_USAGE,
) -> FakeClient:
    """A client that streams `molecules` and then returns them as the final plan."""
    plan = None if refusal else SectionPlan(summary=summary, molecules=molecules)
    return FakeClient(
        FakeCompletions(
            deltas=snapshots(molecules, summary),
            completion=Completion([Choice(Message(parsed=plan, refusal=refusal))], usage=usage),
        )
    )
