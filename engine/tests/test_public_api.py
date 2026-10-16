"""The public API exists with the agreed names; stubs fail loudly until WP5 replaces them."""

import inspect
from pathlib import Path

import pytest

import ecozone_engine as engine

PUBLIC_FUNCTIONS = [
    "load_bundle",
    "summary",
    "layer",
    "hotspots",
    "single_site",
    "rescore",
    "greedy_baseline",
    "shadows",
    "compute_baselines",
]


@pytest.mark.parametrize("name", PUBLIC_FUNCTIONS)
def test_public_function_exists(name: str) -> None:
    assert inspect.isfunction(getattr(engine, name))


def test_stub_raises_not_implemented_yet() -> None:
    with pytest.raises(engine.NotImplementedYetError, match="WP5a"):
        engine.load_bundle(Path("missing"))


def test_change_is_frozen_and_hashable() -> None:
    change = engine.Change(kind="shade", site_id="s_1", quantity=48.0)
    assert hash(change) == hash(engine.Change(kind="shade", site_id="s_1", quantity=48.0))
