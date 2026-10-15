import { GeoJsonLayer } from '@deck.gl/layers'
import { rgba } from '@/lib/colors'
import type { LayerContext } from '../layerRegistry'
import { GROUND_PARAMETERS } from './shared'

export function renderShadows({ data, shadeTime }: LayerContext) {
  const shadows = data.shadows?.[shadeTime]
  if (!shadows) return []
  return [
    new GeoJsonLayer({
      id: 'shadows',
      data: shadows,
      filled: true,
      stroked: false,
      getFillColor: rgba('map-shadow', 55),
      parameters: GROUND_PARAMETERS,
    }),
  ]
}
