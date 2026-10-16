import type { Layer } from '@deck.gl/core'
import { GeoJsonLayer, PolygonLayer, ScatterplotLayer } from '@deck.gl/layers'
import type { Feature, Geometry } from 'geojson'
import type { BuildingChange, InterventionType, Site } from '@/api/types'
import { rgba } from '@/lib/colors'
import { scaleRing } from '@/lib/geo'
import { INTERVENTION_META } from '@/lib/meta'
import type { LayerContext } from '../layerRegistry'
import { GROUND_PARAMETERS, isSelected, type Pickable } from './shared'

interface ChangeProps extends Pickable {
  type: InterventionType
}

/** The working scenario: Repair interventions, or Protect buildings in 3D. */
export function renderChanges(ctx: LayerContext): Layer[] {
  const { scenario } = ctx
  if (scenario.view !== 'scenario' || !scenario.changes.length) return []
  return ctx.mode === 'protect' ? proposedBuildings(ctx) : interventions(ctx)
}

function interventions({ scenario, sites, selection }: LayerContext): Layer[] {
  if (!sites) return []
  const byId = new Map(sites.map((s) => [s.id, s]))
  const chosen = scenario.changes.map((c) => byId.get(c.siteId)).filter((s): s is Site => !!s)
  const areas: Feature<Geometry, ChangeProps>[] = chosen.filter((s) => s.type !== 'tree_row')
    .map((s) => ({ type: 'Feature', geometry: s.geometry, properties: { id: s.id, name: s.name, type: s.type } }))
  const trees = chosen.filter((s) => s.type === 'tree_row')
    .flatMap((s) => (s.points ?? []).map((position) => ({ id: s.id, name: s.name, position })))
  return [
    new GeoJsonLayer<ChangeProps>({
      id: 'changes-areas',
      data: { type: 'FeatureCollection', features: areas },
      pickable: true,
      filled: true,
      stroked: true,
      getFillColor: (f) => rgba(INTERVENTION_META[f.properties.type].color, 190),
      getLineColor: (f) => (isSelected(selection, 'site', f.properties.id) ? rgba('map-selection') : [255, 255, 255, 230]),
      getLineWidth: (f) => (isSelected(selection, 'site', f.properties.id) ? 3 : 1),
      lineWidthUnits: 'pixels',
      updateTriggers: { getLineColor: selection?.id, getLineWidth: selection?.id },
      parameters: GROUND_PARAMETERS,
    }),
    new ScatterplotLayer<(typeof trees)[number]>({
      id: 'changes-trees',
      data: trees,
      pickable: true,
      getPosition: (d) => d.position,
      getRadius: 3,
      radiusUnits: 'meters',
      radiusMinPixels: 2.5,
      getFillColor: (d) => (isSelected(selection, 'site', d.id) ? rgba('map-selection') : rgba('iv-tree', 235)),
      getLineColor: [255, 255, 255, 220],
      stroked: true,
      lineWidthMinPixels: 0.5,
      updateTriggers: { getFillColor: selection?.id },
    }),
  ]
}

function proposedBuildings({ scenario, data, metresPerFloor }: LayerContext): Layer[] {
  const parcels = data.parcels
  if (!parcels) return []
  const byId = new Map(parcels.features.map((f) => [f.properties.id, f]))
  const buildings = scenario.changes.filter((c): c is BuildingChange => c.kind === 'building').flatMap((c) => {
    const parcel = byId.get(c.siteId)
    if (!parcel) return []
    const k = Math.sqrt(c.design.footprintPct / 100)
    return [{
      id: parcel.properties.id,
      name: parcel.properties.name,
      selectKind: 'parcel' as const,
      ring: scaleRing(parcel.geometry.coordinates[0], parcel.properties.center, k),
      height: c.design.floors * metresPerFloor,
    }]
  })
  return [
    new PolygonLayer<(typeof buildings)[number]>({
      id: 'changes-buildings',
      data: buildings,
      pickable: true,
      extruded: true,
      getPolygon: (d) => d.ring,
      getElevation: (d) => d.height,
      getFillColor: rgba('map-proposal', 235),
      material: { ambient: 0.6, diffuse: 0.55, shininess: 12 },
    }),
  ]
}
