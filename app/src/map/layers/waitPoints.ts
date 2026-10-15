import { ScatterplotLayer } from '@deck.gl/layers'
import type { Feature, Point } from 'geojson'
import type { WaitPointProps } from '@/api/types'
import { rgba } from '@/lib/colors'
import type { LayerContext } from '../layerRegistry'
import { isSelected } from './shared'

type WaitPoint = Feature<Point, WaitPointProps>

export function renderWaitPoints({ data, selection }: LayerContext) {
  if (!data.waitPoints) return []
  return [
    new ScatterplotLayer<WaitPoint>({
      id: 'waitPoints',
      data: data.waitPoints.features,
      pickable: true,
      getPosition: (f) => f.geometry.coordinates as [number, number],
      getRadius: (f) => (isSelected(selection, 'waitPoint', f.properties.id) ? 8 : 5),
      radiusUnits: 'pixels',
      getFillColor: (f) => (isSelected(selection, 'waitPoint', f.properties.id) ? rgba('map-selection') : rgba('map-wait-point')),
      getLineColor: [255, 255, 255, 255],
      stroked: true,
      lineWidthMinPixels: 1.5,
      updateTriggers: { getRadius: selection?.id, getFillColor: selection?.id },
    }),
  ]
}
