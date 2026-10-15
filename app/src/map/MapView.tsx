import { useEffect, useMemo, useRef } from 'react'
import { MapboxOverlay } from '@deck.gl/mapbox'
import type { Layer, PickingInfo } from '@deck.gl/core'
import { Map as MaplibreMap, NavigationControl } from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import { useScenario } from '@/state/useScenario'
import { useUiStore } from '@/state/uiStore'
import { layerDefById, layersFor, type LayerContext } from './layerRegistry'
import { pickableOf } from './layers/shared'
import { fitBounds, registerMap } from './mapController'
import { tooltipText } from './tooltip'
import { useMapLayerData } from './useMapLayerData'

// Light, muted basemap with no key (UI_RULES.md §4). Its own buildings and POIs are hidden.
const BASEMAP = 'https://tiles.openfreemap.org/styles/positron'
const HIDDEN_BASEMAP_LAYERS = /building|poi/
const TOOLTIP_STYLE = {
  backgroundColor: 'var(--popover)', color: 'var(--popover-foreground)', border: '1px solid var(--border)',
  borderRadius: '8px', padding: '6px 8px', fontSize: '12px', lineHeight: '1.4', whiteSpace: 'pre-line',
  boxShadow: '0 2px 8px rgb(0 0 0 / 0.08)',
}

export function MapView() {
  const container = useRef<HTMLDivElement>(null)
  const overlay = useRef<MapboxOverlay | null>(null)
  const { area, data, sites } = useMapLayerData()
  const { view, changes, rejected, result } = useScenario()
  const mode = useUiStore((s) => s.mode)
  const visible = useUiStore((s) => s.visibleLayers)
  const shadeTime = useUiStore((s) => s.shadeTime)
  const selection = useUiStore((s) => s.selection)
  const select = useUiStore((s) => s.select)
  const shadeIndex = area ? area.shadeTimes.indexOf(shadeTime) : 0

  useEffect(() => {
    if (!container.current) return
    const map = new MaplibreMap({
      container: container.current,
      style: BASEMAP,
      center: [73.843, 18.5205],
      zoom: 15.6,
      pitch: 40,
      attributionControl: { compact: true },
    })
    map.addControl(new NavigationControl({ visualizePitch: true }), 'top-left')
    map.on('style.load', () => {
      for (const layer of map.getStyle().layers) {
        if (HIDDEN_BASEMAP_LAYERS.test(layer.id)) map.setLayoutProperty(layer.id, 'visibility', 'none')
      }
    })
    const deckOverlay = new MapboxOverlay({ interleaved: false, layers: [] })
    map.addControl(deckOverlay)
    overlay.current = deckOverlay
    registerMap(map)
    const clear = (e: KeyboardEvent) => e.key === 'Escape' && useUiStore.getState().select(null)
    window.addEventListener('keydown', clear)
    return () => {
      window.removeEventListener('keydown', clear)
      registerMap(null)
      map.remove()
    }
  }, [])

  useEffect(() => {
    if (area) fitBounds(area.bbox)
  }, [area])

  const { blocks, segments, buildings, waitPoints, parcels, shadows } = data
  const layers = useMemo(() => {
    const ctx: LayerContext = {
      mode,
      data: { blocks, segments, buildings, waitPoints, parcels, shadows },
      sites,
      shadeTime,
      shadeIndex,
      selection,
      scenario: { view, changes, rejected, result },
      metresPerFloor: area?.engine.metresPerFloor ?? 3,
    }
    return layersFor(mode).filter((l) => visible[l.id as keyof typeof visible]).flatMap((l): Layer[] => l.render(ctx))
  }, [mode, blocks, segments, buildings, waitPoints, parcels, shadows, sites, visible, shadeTime, shadeIndex, selection, view, changes, rejected, result, area])

  useEffect(() => {
    overlay.current?.setProps({
      layers,
      onClick: (info: PickingInfo) => {
        const def = layerDefById(info.layer?.id ?? '')
        const picked = pickableOf(info.object)
        const kind = picked?.selectKind ?? def?.selects
        select(picked && kind ? { kind, id: picked.id } : null)
      },
      getTooltip: (info: PickingInfo) => {
        const def = layerDefById(info.layer?.id ?? '')
        const picked = pickableOf(info.object)
        const kind = picked?.selectKind ?? def?.selects
        if (!picked || !kind) return null
        const props = (info.object as { properties?: unknown }).properties ?? info.object
        return { text: tooltipText(kind, props, shadeIndex, shadeTime), style: TOOLTIP_STYLE }
      },
    })
  }, [layers, select, shadeIndex, shadeTime])

  // MapLibre's stylesheet sets position: relative on its container, so the container fills a positioned wrapper.
  return (
    <div className="absolute inset-0">
      <div ref={container} className="size-full" aria-label="Map of the selected area" role="region" />
    </div>
  )
}
