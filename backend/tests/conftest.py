"""Fixtures. Deliberately no network and no OpenAI client anywhere.

The one thing these tests must never do is call the model: the answer would
change between runs, the assertions would have to be vague enough to survive
that, and a vague assertion about a generated interface is worth nothing.

So the model boundary is faked. Everything below it -- the sanitiser, the
compiler, the walkthrough, the routes, the fallbacks -- is the real code.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.core.config import Settings
from app.main import create_app
from app.schemas import (
    Callout,
    Metric,
    MetricGrid,
    Molecule,
    Phase,
    PhasePlan,
    ScoreRow,
    ScoreTable,
)


@pytest.fixture
def no_key_settings() -> Settings:
    """Settings with no API key, which is the fallback path every route has."""
    return Settings(openai_api_key=SecretStr(""), openai_model="test-model", log_level="WARNING")


@pytest.fixture
def keyed_settings() -> Settings:
    """Settings that look configured. Never used to actually authenticate."""
    return Settings(
        openai_api_key=SecretStr("test-key-not-a-real-credential"),
        openai_model="test-model",
        log_level="WARNING",
    )


@pytest.fixture
def client(no_key_settings: Settings) -> Iterator[TestClient]:
    """The app, built with keyless settings so no test can reach the network."""
    app = create_app(no_key_settings)
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def callout() -> Callout:
    """A complete, drawable callout."""
    return Callout(
        tone="context",
        lead="Budget stated.",
        body="The document publishes an envelope in §4.",
        label="Budget signals",
        source="Opportunity document §4",
        inspect=True,
    )


@pytest.fixture
def metric_grid() -> MetricGrid:
    """A three-tile grid, the minimum the schema allows."""
    return MetricGrid(
        metrics=[
            Metric(label="Recommendation", value="Pursue", sub="A verdict."),
            Metric(label="Est. budget", value="$180-220K"),
            Metric(label="Timeline", value="14 days"),
        ]
    )


@pytest.fixture
def score_table() -> ScoreTable:
    """A scored table with an aligned total."""
    row = ScoreRow(name="Clinical safety", weight="30%", score="4.5", band="high", note="Strong.")
    return ScoreTable(rows=[row], total=row)


@pytest.fixture
def phase_plan() -> PhasePlan:
    """A two-phase plan, the minimum the schema allows."""
    return PhasePlan(
        phases=[
            Phase(tag="Phase 1", name="Response", when="Weeks 1-2", scope=["Write it."]),
            Phase(tag="Phase 2", name="Shortlist", when="By day 10"),
        ]
    )


@pytest.fixture
def molecules(metric_grid: MetricGrid, callout: Callout, score_table: ScoreTable) -> list[Molecule]:
    """A small mixed section, in render order."""
    return [metric_grid, callout, score_table]
