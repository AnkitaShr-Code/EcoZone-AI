import { GeoJsonLayer } from '@deck.gl/layers'
import type { ParcelProps } from '@/api/types'
import { rgba } from '@/lib/colors'
import type { LayerContext } from '../layerRegistry'
import { GROUND_PARAMETERS, isSelected } from './shared'

/** Vacant plots that Protect can test a building on. */
export function renderParcels({ data, selection }: LayerContext) {
  if (!data.parcels) return []
  return [
    new GeoJsonLayer<ParcelProps>({
      id: 'parcels',
      data: data.parcels,
      pickable: true,
      filled: true,
      stroked: true,
      getFillColor: (f) => rgba('map-parcel', isSelected(selection, 'parcel', f.properties.id) ? 90 : 45),
      getLineColor: (f) => (isSelected(selection, 'parcel', f.properties.id) ? rgba('map-selection') : rgba('map-parcel', 220)),
      getLineWidth: (f) => (isSelected(selection, 'parcel', f.properties.id) ? 3 : 1.5),
      lineWidthUnits: 'pixels',
      updateTriggers: { getFillColor: selection?.id, getLineColor: selection?.id, getLineWidth: selection?.id },
      parameters: GROUND_PARAMETERS,
    }),
  ]
}
