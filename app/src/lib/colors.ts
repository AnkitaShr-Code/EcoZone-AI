// Map colours as RGBA arrays for deck.gl, read from the CSS tokens in
// styles/globals.css so the UI and the map never disagree (UI_RULES.md §5).

export type Rgba = [number, number, number, number]

export type ColorToken =
  | 'data-sun' | 'data-shade'
  | 'priority-high' | 'priority-medium' | 'priority-low'
  | 'iv-tree' | 'iv-shade' | 'iv-depave' | 'iv-green' | 'iv-roof'
  | 'status-rejected'
  | 'map-building' | 'map-wait-point' | 'map-shadow' | 'map-selection'

const cache = new Map<ColorToken, [number, number, number]>()

function resolve(token: ColorToken): [number, number, number] {
  const cached = cache.get(token)
  if (cached) return cached
  const value = getComputedStyle(document.documentElement).getPropertyValue(`--${token}`).trim()
  // Let the browser parse any CSS colour (hex, rgb, oklch) via a 1×1 canvas.
  const ctx = document.createElement('canvas').getContext('2d')
  let rgb: [number, number, number] = [128, 128, 128]
  if (ctx && value) {
    ctx.fillStyle = value
    ctx.fillRect(0, 0, 1, 1)
    const [r, g, b] = ctx.getImageData(0, 0, 1, 1).data
    rgb = [r, g, b]
  }
  cache.set(token, rgb)
  return rgb
}

export function rgba(token: ColorToken, alpha = 255): Rgba {
  return [...resolve(token), alpha]
}

/** CSS reference for the same token, for legends and badges. */
export function cssVar(token: ColorToken): string {
  return `var(--${token})`
}
