"""ecozone_engine public API (engine/RULES.md, "Public API").

`api`, `agents` and `pipeline` import only these names. Signatures are an interface between
work packages: changing one is its own PR, agreed by the engine and API owners.
"""

from ._stub import NotImplementedYetError
from .errors import (
    EngineInputError,
    InvalidBundleError,
    InvalidChangeError,
    QuantityOutOfRangeError,
    UnknownParcelError,
    UnknownSiteError,
)
from .greedy import greedy_baseline
from .io import load_bundle
from .model import (
    AreaModel,
    AreaResultData,
    AreaScores,
    AreaSummaryData,
    BaselineData,
    BlockResult,
    Change,
    ChangeKind,
    Feature,
    HotspotData,
    IndexKey,
    InterventionKind,
    LayerName,
    PortfolioData,
    PriorityClass,
    RiskInfo,
    RiskLabel,
    Scores,
    ShadeByTime,
    ShadeTime,
    SingleSiteData,
    UnitCost,
    UnitCosts,
)
from .queries import compute_baselines, hotspots, layer, single_site, summary
from .rescore import rescore
from .shadows import shadows

__all__ = [
    "AreaModel",
    "AreaResultData",
    "AreaScores",
    "AreaSummaryData",
    "BaselineData",
    "BlockResult",
    "Change",
    "ChangeKind",
    "EngineInputError",
    "Feature",
    "HotspotData",
    "IndexKey",
    "InterventionKind",
    "InvalidBundleError",
    "InvalidChangeError",
    "LayerName",
    "NotImplementedYetError",
    "PortfolioData",
    "PriorityClass",
    "QuantityOutOfRangeError",
    "RiskInfo",
    "RiskLabel",
    "Scores",
    "ShadeByTime",
    "ShadeTime",
    "SingleSiteData",
    "UnitCost",
    "UnitCosts",
    "UnknownParcelError",
    "UnknownSiteError",
    "compute_baselines",
    "greedy_baseline",
    "hotspots",
    "layer",
    "load_bundle",
    "rescore",
    "shadows",
    "single_site",
    "summary",
]
