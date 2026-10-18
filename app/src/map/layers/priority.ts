import { GeoJsonLayer } from '@deck.gl/layers'
import type { BlockProps } from '@/api/types'
import { rgba } from '@/lib/colors'
import { PRIORITY_META } from '@/lib/meta'
import type { LayerContext } from '../layerRegistry'
import { GROUND_PARAMETERS, isSelected } from './shared'

// Sequential heat ramp; higher alpha now that the basemap is dimmed (UI_RULES.md §1).
const FILL_ALPHA = { high: 200, medium: 140, low: 70 } as const

export function renderPriority({ data, selection }: LayerContext) {
  if (!data.blocks) return []
  return [
    new GeoJsonLayer<BlockProps>({
      id: 'priority',
      data: data.blocks,
      pickable: true,
      filled: true,
      stroked: true,
      getFillColor: (f) =>
        rgba(PRIORITY_META[f.properties.priorityClass].color, FILL_ALPHA[f.properties.priorityClass]),
      getLineColor: (f) =>
        isSelected(selection, 'block', f.properties.id) ? rgba('map-selection') : [255, 255, 255, 200],
      getLineWidth: (f) => (isSelected(selection, 'block', f.properties.id) ? 3 : 1),
      lineWidthUnits: 'pixels',
      updateTriggers: { getLineColor: selection?.id, getLineWidth: selection?.id },
      parameters: GROUND_PARAMETERS,
    }),
  ]
}
