"""Every prototype setting, each citing its docs/PLANNING.md section (engine/RULES.md, "Settings, not literals").

Filled in by the engine owner in WP5; one frozen dataclass so settings hash into the bundle meta.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EngineSettings:
    """Placeholder until WP5a adds the weights, thresholds and radii."""


SETTINGS = EngineSettings()
