import { useArea, useLayer } from '@/api/hooks'
import type { LayerData, LayerName } from '@/api/types'
import { useUiStore } from '@/state/uiStore'
import { LAYERS } from './layerRegistry'

/** Loads only the layer data that visible layers need. */
export function useMapLayerData() {
  const areaId = useUiStore((s) => s.areaId)
  const visible = useUiStore((s) => s.visibleLayers)
  const needed = new Set<LayerName>(LAYERS.filter((l) => visible[l.id]).flatMap((l) => l.needs))

  const area = useArea(areaId)
  const blocks = useLayer(areaId, 'blocks', needed.has('blocks'))
  const segments = useLayer(areaId, 'segments', needed.has('segments'))
  const buildings = useLayer(areaId, 'buildings', needed.has('buildings'))
  const waitPoints = useLayer(areaId, 'waitPoints', needed.has('waitPoints'))
  const shadows = useLayer(areaId, 'shadows', needed.has('shadows'))

  const data: Partial<LayerData> = {
    blocks: blocks.data,
    segments: segments.data,
    buildings: buildings.data,
    waitPoints: waitPoints.data,
    shadows: shadows.data,
  }
  const loading = [blocks, segments, buildings, waitPoints, shadows].some((q) => q.isFetching)
  return { area: area.data, data, loading }
}
