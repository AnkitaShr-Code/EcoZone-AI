"""Minimal GeoJSON geometry and feature shapes, WGS84, as served to the map."""

from typing import Annotated, Literal

from pydantic import Field

from .common import ContractModel, LonLat


class PointGeometry(ContractModel):
    type: Literal["Point"]
    coordinates: LonLat


class LineStringGeometry(ContractModel):
    type: Literal["LineString"]
    coordinates: list[LonLat]


class PolygonGeometry(ContractModel):
    type: Literal["Polygon"]
    coordinates: list[list[LonLat]]


class MultiPolygonGeometry(ContractModel):
    type: Literal["MultiPolygon"]
    coordinates: list[list[list[LonLat]]]


SiteGeometry = Annotated[LineStringGeometry | PolygonGeometry | MultiPolygonGeometry, Field(discriminator="type")]
