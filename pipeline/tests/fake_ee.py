"""A numpy stand-in for the slice of the `ee` module that `steps/earth_engine.py` uses, so the Earth Engine step runs
offline. Pixels are points on a grid; every image shares the grid. It evaluates eagerly instead of building a server
graph, but implements the same method names and semantics (masks propagate, `updateMask` ANDs, the median ignores masked
values), which is what the tests exercise."""

from __future__ import annotations

import warnings
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import shapely
from shapely.geometry import shape


class FakeImage:
    def __init__(self, bands: dict[str, np.ndarray], mask: np.ndarray, xy: np.ndarray) -> None:
        self.bands = bands
        self.mask = mask
        self.xy = xy
        self.last_call: dict[str, Any] = {}

    def _only(self) -> np.ndarray:
        (values,) = self.bands.values()
        return values

    def _like(self, values: np.ndarray, name: str | None = None) -> FakeImage:
        key = name or next(iter(self.bands))
        return FakeImage({key: values.astype(float)}, self.mask.copy(), self.xy)

    def select(self, name: str) -> FakeImage:
        return FakeImage({name: self.bands[name]}, self.mask.copy(), self.xy)

    def rename(self, name: str) -> FakeImage:
        return self._like(self._only(), name)

    def multiply(self, k: float) -> FakeImage:
        return self._like(self._only() * k)

    def add(self, k: float) -> FakeImage:
        return self._like(self._only() + k)

    def bitwiseAnd(self, k: int) -> FakeImage:  # noqa: N802
        return self._like(self._only().astype(np.int64) & int(k))

    def eq(self, k: float) -> FakeImage:
        return self._like(self._only() == k)

    def gt(self, k: float) -> FakeImage:
        return self._like(self._only() > k)

    def gte(self, k: float) -> FakeImage:
        return self._like(self._only() >= k)

    def lte(self, k: float) -> FakeImage:
        return self._like(self._only() <= k)

    def And(self, other: FakeImage) -> FakeImage:  # noqa: N802
        return self._like((self._only() != 0) & (other._only() != 0))

    def updateMask(self, other: FakeImage) -> FakeImage:  # noqa: N802
        return FakeImage(dict(self.bands), self.mask & other.mask & (other._only() != 0), self.xy)

    def reduceRegions(  # noqa: N802
        self, collection: FakeFeatureCollection, reducer: Any, scale: int, crs: str
    ) -> FakeResult:
        assert isinstance(reducer, FakeReducer) and reducer.names == ["median", "count"]
        values = self._only()
        out: list[dict[str, Any]] = []
        for feature in collection.features:
            inside = shapely.contains_xy(feature.geometry.shape, self.xy[:, 0], self.xy[:, 1])
            picked = values[inside & self.mask]
            props: dict[str, Any] = {**feature.props, "count": float(picked.size)}
            if picked.size:
                props["median"] = float(np.median(picked))
            out.append({"properties": props})
        self.last_call = {"scale": scale, "crs": crs}
        return FakeResult({"features": out})


@dataclass
class FakeResult:
    value: Any

    def getInfo(self) -> Any:  # noqa: N802
        return self.value


@dataclass
class Scene:
    dataset: str
    date: str
    props: dict[str, float]
    bands: dict[str, np.ndarray]
    mask: np.ndarray | None = None


class FakeCollection:
    def __init__(self, ee: FakeEe, scenes: list[Scene]) -> None:
        self.ee = ee
        self.scenes = scenes
        self.mapped: list[FakeImage] | None = None

    def filterBounds(self, geometry: FakeGeometry) -> FakeCollection:  # noqa: N802
        self.ee.calls.append(("filterBounds", geometry.bounds))
        return self

    def filterDate(self, start: str, end: str) -> FakeCollection:  # noqa: N802
        self.ee.calls.append(("filterDate", (start, end)))
        return FakeCollection(self.ee, [s for s in self.scenes if start <= s.date < end])

    def filter(self, f: FakeFilter) -> FakeCollection:
        return FakeCollection(self.ee, [s for s in self.scenes if f(s.props)])

    def merge(self, other: FakeCollection) -> FakeCollection:
        return FakeCollection(self.ee, [*self.scenes, *other.scenes])

    def size(self) -> FakeResult:
        return FakeResult(len(self.scenes))

    def _images(self) -> list[FakeImage]:
        xy = self.ee.xy
        return [
            FakeImage(
                {k: np.asarray(v, dtype=float) for k, v in s.bands.items()},
                np.ones(len(xy), bool) if s.mask is None else s.mask,
                xy,
            )
            for s in self.scenes
        ]

    def map(self, fn: Callable[[FakeImage], FakeImage]) -> FakeCollection:
        out = FakeCollection(self.ee, self.scenes)
        out.mapped = [fn(i) for i in self._images()]
        return out

    def median(self) -> FakeImage:
        assert self.mapped is not None
        stack = np.stack([np.where(i.mask, i._only(), np.nan) for i in self.mapped])
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)  # all-masked pixels are NaN on purpose
            med = np.nanmedian(stack, axis=0)
        return FakeImage({"LST_K": np.nan_to_num(med)}, ~np.isnan(med), self.ee.xy)


@dataclass
class FakeFilter:
    prop: str
    limit: float

    def __call__(self, props: dict[str, float]) -> bool:
        return props[self.prop] < self.limit


class FakeGeometry:
    def __init__(self, geojson: dict[str, Any] | None = None, proj: str | None = None, geodesic: bool | None = None):
        self.geojson = geojson
        self.proj = proj
        self.geodesic = geodesic
        self.bounds: list[float] | None = None

    @property
    def shape(self) -> Any:
        assert self.geojson is not None
        return shape(self.geojson)

    @staticmethod
    def Rectangle(coords: list[float]) -> FakeGeometry:  # noqa: N802
        g = FakeGeometry()
        g.bounds = coords
        return g


@dataclass
class FakeFeature:
    geometry: FakeGeometry
    props: dict[str, Any]


@dataclass
class FakeFeatureCollection:
    features: list[FakeFeature]


@dataclass
class FakeReducer:
    names: list[str] = field(default_factory=list[str])

    def combine(self, other: FakeReducer, sharedInputs: bool = False) -> FakeReducer:  # noqa: N803
        assert sharedInputs
        return FakeReducer([*self.names, *other.names])


class FakeEe:
    """Registry of scenes per dataset id plus the `ee` names the step calls."""

    __version__ = "0.0-fake"

    def __init__(self, xy: np.ndarray, scenes: list[Scene]) -> None:
        self.xy = xy
        self.scenes = scenes
        self.calls: list[tuple[str, Any]] = []
        self.initialize_kwargs: list[dict[str, Any]] = []
        self.fail_initialize: Exception | None = None
        self.Geometry = FakeGeometry
        self.Filter = type("Filter", (), {"lt": staticmethod(lambda prop, v: FakeFilter(prop, v))})
        self.Reducer = type(
            "Reducer",
            (),
            {
                "median": staticmethod(lambda: FakeReducer(["median"])),
                "count": staticmethod(lambda: FakeReducer(["count"])),
            },
        )

    def Initialize(self, **kwargs: Any) -> None:  # noqa: N802
        if self.fail_initialize is not None:
            raise self.fail_initialize
        self.initialize_kwargs.append(kwargs)

    def ImageCollection(self, dataset_id: str) -> FakeCollection:  # noqa: N802
        self.calls.append(("ImageCollection", dataset_id))
        return FakeCollection(self, [s for s in self.scenes if s.dataset == dataset_id])

    def Feature(self, geometry: FakeGeometry, props: dict[str, Any]) -> FakeFeature:  # noqa: N802
        return FakeFeature(geometry, props)

    def FeatureCollection(self, features: list[FakeFeature]) -> FakeFeatureCollection:  # noqa: N802
        return FakeFeatureCollection(features)
