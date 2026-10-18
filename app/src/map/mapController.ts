// A handle on the single map instance, so panel actions (for example clicking a
// hotspot) can move the camera without passing refs through the tree.

import type { Map as MaplibreMap } from 'maplibre-gl'

let map: MaplibreMap | null = null

export function registerMap(instance: MaplibreMap | null) {
  map = instance
}

export function flyTo(center: [number, number], zoom = 17) {
  map?.flyTo({ center, zoom, duration: 900, essential: true })
}

export function fitBounds(bbox: [number, number, number, number]) {
  // Left padding clears the 380 px side panel; pitch 45 makes extruded buildings readable.
  map?.fitBounds([[bbox[0], bbox[1]], [bbox[2], bbox[3]]], {
    padding: { top: 40, right: 60, bottom: 60, left: 420 },
    pitch: 45,
    duration: 0,
  })
}
