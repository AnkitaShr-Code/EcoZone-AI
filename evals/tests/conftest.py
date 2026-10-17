"""Unit tests of the eval helpers. They need none of the eval session's bundle rows, so the recorder fixture is off."""

import pytest


@pytest.fixture(scope="session", autouse=True)
def _record_session() -> None:  # pyright: ignore[reportUnusedFunction]
    """Overrides evals/conftest.py: no bundle or machine rows for unit tests."""
