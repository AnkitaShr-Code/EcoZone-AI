// Display geometry helpers. Never used to compute scores (UI_RULES.md §1, principle 4).

const EARTH_RADIUS_M = 6371000

export function distanceM(a: [number, number], b: [number, number]): number {
  const toRad = (d: number) => (d * Math.PI) / 180
  const dLat = toRad(b[1] - a[1])
  const dLon = toRad(b[0] - a[0])
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(toRad(a[1])) * Math.cos(toRad(b[1])) * Math.sin(dLon / 2) ** 2
  return 2 * EARTH_RADIUS_M * Math.asin(Math.sqrt(h))
}

/** Scale a ring about a centre point, for drawing a building footprint inside its plot. */
export function scaleRing(ring: number[][], center: [number, number], k: number): [number, number][] {
  return ring.map(([x, y]) => [center[0] + (x - center[0]) * k, center[1] + (y - center[1]) * k])
}

/** A point to fly to for any site geometry. */
export function centerOf(geometry: { type: string; coordinates: unknown }): [number, number] {
  const flat: number[][] = []
  const walk = (c: unknown) => {
    if (Array.isArray(c) && typeof c[0] === 'number') flat.push(c as number[])
    else if (Array.isArray(c)) c.forEach(walk)
  }
  walk(geometry.coordinates)
  const sum = flat.reduce((a, p) => [a[0] + p[0], a[1] + p[1]], [0, 0])
  return [sum[0] / flat.length, sum[1] / flat.length]
}
