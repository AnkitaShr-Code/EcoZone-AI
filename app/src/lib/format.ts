// Every displayed number goes through these (UI_RULES.md §6, §8).

const LAKH = 1e5
const CRORE = 1e7

/** Index score, 0–100, rounded: "64". Pair with "/ 100" in the UI where space allows. */
export function formatScore(value: number): string {
  return String(Math.round(value))
}

/** Signed change with an arrow: "↑ 7", "↓ 3", "No change". */
export function formatDelta(delta: number): string {
  const rounded = Math.round(delta)
  if (rounded === 0) return 'No change'
  return `${rounded > 0 ? '↑' : '↓'} ${Math.abs(rounded)}`
}

/** Indian rupees in lakh or crore for large values: "₹ 25 lakh", "₹ 3.2 lakh", "₹ 4,500". */
export function formatInr(value: number): string {
  if (value >= CRORE) return `₹ ${trim(value / CRORE)} crore`
  if (value >= LAKH) return `₹ ${trim(value / LAKH)} lakh`
  return `₹ ${Math.round(value).toLocaleString('en-IN')}`
}

export function formatPercent(value: number): string {
  return `${Math.round(value)}%`
}

export function formatCount(value: number, singular: string, plural = `${singular}s`): string {
  return `${value.toLocaleString('en-IN')} ${value === 1 ? singular : plural}`
}

/** "13:00" → "1 pm". */
export function formatShadeTime(time: string): string {
  const [h, m] = time.split(':').map(Number)
  const h12 = ((h + 11) % 12) + 1
  return `${h12}${m ? `:${String(m).padStart(2, '0')}` : ''} ${h < 12 ? 'am' : 'pm'}`
}

/** "12 floors · 60% footprint · 10% green · long side 105°". */
export function formatDesign(d: { floors: number; footprintPct: number; greenPct: number; orientationDeg: number }): string {
  return `${d.floors} floors · ${d.footprintPct}% footprint · ${d.greenPct}% green · long side ${d.orientationDeg}°`
}

/** "2026-04-15" → "15 April". */
export function formatReferenceDate(date: string): string {
  return new Date(`${date}T00:00:00`).toLocaleDateString('en-IN', { day: 'numeric', month: 'long' })
}

function trim(n: number): string {
  return n.toFixed(n >= 100 ? 0 : 1).replace(/\.0$/, '')
}

/** "Block 12" from a block id; ids carry a type prefix (`blk_12`, mock `bk012`). */
export function formatBlock(id: string): string {
  return `Block ${id.replace(/^\D+/, '')}`
}
