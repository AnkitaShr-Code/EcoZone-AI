"""ecozone_agents: the shared search loop, proposers, writer, output guard and template fallback (agents/RULES.md).

The API imports `AgentsRunner` and `build_runner`; everything else is internal or used by tests.
"""

from .config import AgentSettings
from .runner import AgentsRunner, build_runner

__all__ = ["AgentSettings", "AgentsRunner", "build_runner"]
