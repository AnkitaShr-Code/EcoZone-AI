import { GeoJsonLayer } from '@deck.gl/layers'
import type { BuildingProps } from '@/api/types'
import { rgba } from '@/lib/colors'
import type { LayerContext } from '../layerRegistry'

export function renderBuildings({ data }: LayerContext) {
  if (!data.buildings) return []
  return [
    new GeoJsonLayer<BuildingProps>({
      id: 'buildings',
      data: data.buildings,
      extruded: true,
      filled: true,
      stroked: false,
      getElevation: (f) => f.properties.heightM,
      getFillColor: rgba('map-building', 235),
      material: { ambient: 0.65, diffuse: 0.5, shininess: 8 },
    }),
  ]
}
