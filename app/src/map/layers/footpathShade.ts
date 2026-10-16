import { PathLayer } from '@deck.gl/layers'
import type { Feature, LineString } from 'geojson'
import type { SegmentProps } from '@/api/types'
import { rgba } from '@/lib/colors'
import type { LayerContext } from '../layerRegistry'
import { GROUND_PARAMETERS, isSelected } from './shared'

type Segment = Feature<LineString, SegmentProps>

export function renderFootpathShade({ data, shadeIndex, selection, scenario }: LayerContext) {
  if (!data.segments) return []
  // With the scenario view on, changed segments take their new shade state from the rescore result.
  const overrides = scenario.view === 'scenario' ? scenario.result?.segments : undefined
  return [
    new PathLayer<Segment>({
      id: 'footpathShade',
      data: data.segments.features,
      pickable: true,
      getPath: (f) => f.geometry.coordinates as [number, number][],
      getColor: (f) => {
        if (isSelected(selection, 'segment', f.properties.id)) return rgba('map-selection')
        const shaded = (overrides?.[f.properties.id] ?? f.properties.shaded)[shadeIndex]
        return shaded ? rgba('data-shade') : rgba('data-sun')
      },
      getWidth: 2.5,
      widthUnits: 'meters',
      widthMinPixels: 2,
      capRounded: true,
      updateTriggers: { getColor: [shadeIndex, selection?.id, overrides] },
      parameters: GROUND_PARAMETERS,
    }),
  ]
}
