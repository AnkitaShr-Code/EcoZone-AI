// Prepared, cached lookups over one area's mock data, so rescoring a change set
// takes milliseconds (the real engine does the same with STRtree indexes).

import type { FeatureCollection, LineString, Polygon } from 'geojson'
import type { AreaSummary, BlockProps, ParcelProps, SegmentProps, Site } from '../types'

export interface AreaIndex {
  area: AreaSummary
  blocks: BlockProps[]
  blockById: Map<string, BlockProps>
  segments: SegmentProps[]
  segmentById: Map<string, SegmentProps>
  segmentsByBlock: Map<string, SegmentProps[]>
  sites: Site[]
  siteById: Map<string, Site>
  parcels: ParcelProps[]
  parcelById: Map<string, ParcelProps>
}

export function buildAreaIndex(
  area: AreaSummary,
  blocks: FeatureCollection<Polygon, BlockProps>,
  segments: FeatureCollection<LineString, SegmentProps>,
  sites: Site[],
  parcels: FeatureCollection<Polygon, ParcelProps>,
): AreaIndex {
  const blockProps = blocks.features.map((f) => f.properties)
  const segmentProps = segments.features.map((f) => f.properties)
  const segmentsByBlock = new Map<string, SegmentProps[]>()
  for (const s of segmentProps) {
    if (!s.block) continue
    const list = segmentsByBlock.get(s.block) ?? []
    list.push(s)
    segmentsByBlock.set(s.block, list)
  }
  const parcelProps = parcels.features.map((f) => f.properties)
  return {
    area,
    blocks: blockProps,
    blockById: new Map(blockProps.map((b) => [b.id, b])),
    segments: segmentProps,
    segmentById: new Map(segmentProps.map((s) => [s.id, s])),
    segmentsByBlock,
    sites,
    siteById: new Map(sites.map((s) => [s.id, s])),
    parcels: parcelProps,
    parcelById: new Map(parcelProps.map((p) => [p.id, p])),
  }
}
