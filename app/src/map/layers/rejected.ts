import { PathLayer } from '@deck.gl/layers'
import type { LineString } from 'geojson'
import { rgba } from '@/lib/colors'
import type { LayerContext } from '../layerRegistry'
import { GROUND_PARAMETERS, isSelected } from './shared'

/** Repair options the engine rejected (for example tree rows that would block the breeze). */
export function renderRejected({ scenario, sites, selection }: LayerContext) {
  if (scenario.view !== 'scenario' || !scenario.rejected.length || !sites) return []
  const ids = new Set(scenario.rejected.map((r) => r.siteId))
  const lines = sites.filter((s) => ids.has(s.id) && s.geometry.type === 'LineString')
    .map((s) => ({ id: s.id, name: s.name, path: (s.geometry as LineString).coordinates as [number, number][] }))
  return [
    new PathLayer<(typeof lines)[number]>({
      id: 'rejected',
      data: lines,
      pickable: true,
      getPath: (d) => d.path,
      getColor: (d) => (isSelected(selection, 'site', d.id) ? rgba('map-selection') : rgba('status-rejected', 220)),
      getWidth: 3,
      widthUnits: 'meters',
      widthMinPixels: 3,
      capRounded: true,
      updateTriggers: { getColor: selection?.id },
      parameters: GROUND_PARAMETERS,
    }),
  ]
}
