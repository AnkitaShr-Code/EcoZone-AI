// API types. Wire shapes are generated from contract/openapi.json (`npm run gen:api`) and
// re-exported here; this file only names and narrows them (ENGINEERING_RULES.md §6). Never
// hand-define a wire shape here: change the Pydantic model in contract/ instead.

import type { FeatureCollection, LineString, Point, Polygon } from 'geojson'
import type { components } from './generated'

type S = components['schemas']

export type AreaSummary = S['AreaSummary']
export type AreaScores = S['AreaScores']
export type Scores = S['Scores']
export type UnitCost = S['UnitCost']
export type UnitCosts = S['UnitCosts']
export type DataGaps = S['DataGaps']

export type BlockProps = S['BlockProps']
export type SegmentProps = S['SegmentProps']
export type BuildingProps = S['BuildingProps']
export type WaitPointProps = S['WaitPointProps']
export type ParcelProps = S['ParcelProps']
export type ShadowProps = S['EmptyProps']

export type Hotspot = S['Hotspot']
export type Site = S['Site']
export type SingleSiteResult = S['SingleSiteResult']
export type Change = S['Change']
export type InterventionChange = S['InterventionChange']
export type BuildingChange = S['BuildingChange']
export type BuildingDesign = S['BuildingDesign']
export type RescoreRequest = S['RescoreRequest']
export type AreaResult = S['AreaResult']
export type BlockResult = S['BlockResult']
export type RiskInfo = S['RiskInfo']
export type RejectedOption = S['RejectedOption']

export type SearchRequest = S['SearchRequest']
export type Candidate = S['Candidate']
export type DesignOption = S['DesignOption']
export type SearchResult = S['SearchResult']
export type SearchEvent = S['SearchEvent']
export type Explanation = S['Explanation']
export type ErrorBody = S['ErrorBody']

// ---------- named closed sets, taken from the generated models ----------

export type Mode = S['RepairSearchRequest']['mode'] | S['ProtectSearchRequest']['mode']
export type ShadeTime = AreaSummary['shadeTimes'][number]
export type InterventionType = S['Site']['type']
export type PriorityClass = Hotspot['priorityClass']
export type IndexKey = RiskInfo['index']
export type RiskLabel = RiskInfo['label']
export type TimeToBenefit = Site['timeToBenefit']
export type HeightSource = BuildingProps['heightSource']
export type DriverTag = Hotspot['drivers'][number]
export type ShadeByTime = SegmentProps['shaded']

// ---------- map layers, typed for deck.gl's GeoJSON ----------

/** Map layers served by GET /api/areas/{area}/layers/{name} and /shadows. */
export interface LayerData {
  blocks: FeatureCollection<Polygon, BlockProps>
  segments: FeatureCollection<LineString, SegmentProps>
  buildings: FeatureCollection<Polygon, BuildingProps>
  waitPoints: FeatureCollection<Point, WaitPointProps>
  parcels: FeatureCollection<Polygon, ParcelProps>
  shadows: Record<ShadeTime, FeatureCollection<Polygon, ShadowProps>>
}
export type LayerName = keyof LayerData
