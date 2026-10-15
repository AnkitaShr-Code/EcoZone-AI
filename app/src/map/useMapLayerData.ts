import { useArea, useLayer, useSites } from '@/api/hooks'
import type { LayerData, LayerName } from '@/api/types'
import { useUiStore } from '@/state/uiStore'
import { layersFor } from './layerRegistry'

/** Loads only the data that the visible layers of the current mode need. */
export function useMapLayerData() {
  const areaId = useUiStore((s) => s.areaId)
  const mode = useUiStore((s) => s.mode)
  const visible = useUiStore((s) => s.visibleLayers)
  const shown = layersFor(mode).filter((l) => visible[l.id as keyof typeof visible])
  const needed = new Set<LayerName>(shown.flatMap((l) => l.needs))

  const area = useArea(areaId)
  const blocks = useLayer(areaId, 'blocks', needed.has('blocks'))
  const segments = useLayer(areaId, 'segments', needed.has('segments'))
  const buildings = useLayer(areaId, 'buildings', needed.has('buildings'))
  const waitPoints = useLayer(areaId, 'waitPoints', needed.has('waitPoints'))
  const parcels = useLayer(areaId, 'parcels', needed.has('parcels'))
  const shadows = useLayer(areaId, 'shadows', needed.has('shadows'))
  const sites = useSites(areaId, mode === 'repair' && shown.some((l) => l.needsSites))

  const data: Partial<LayerData> = {
    blocks: blocks.data,
    segments: segments.data,
    buildings: buildings.data,
    waitPoints: waitPoints.data,
    parcels: parcels.data,
    shadows: shadows.data,
  }
  return { area: area.data, data, sites: sites.data }
}
