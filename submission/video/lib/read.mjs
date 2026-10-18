// Read real values from the app's DOM. Everything the narration says comes from here.

const STAT_RE = /(Area cooling score|Footpath shade|Heat exposure|Green connectivity|Ventilation)\n(\d+(?:\.\d+)?)\n\/ 100(?:\n(↑ ?\d+(?:\.\d+)?|↓ ?\d+(?:\.\d+)?|No change)(?:\n, (better|worse))?)?/g;

/** Parse "Label\n35\n/ 100\n↑ 5\n, better" stat cards from a block of innerText. */
export function parseStats(text) {
  const out = {};
  for (const m of text.matchAll(STAT_RE)) {
    const [, label, value, delta, dir] = m;
    if (out[label]) continue;
    let d = null;
    if (delta && delta !== 'No change') d = (delta.startsWith('↓') ? -1 : 1) * Number(delta.replace(/[↑↓ ]/g, ''));
    if (delta === 'No change') d = 0;
    out[label] = { value: Number(value), delta: d, deltaText: delta ?? null, direction: dir ?? null };
  }
  return out;
}

export async function asideText(page) {
  return page.locator('aside').innerText();
}

/** Bounding box in video pixels (CSS px times the device scale factor). */
export async function boxOf(locator, scale) {
  const b = await locator.boundingBox({ timeout: 4000 });
  if (!b) throw new Error('not visible');
  return { x: Math.round(b.x * scale), y: Math.round(b.y * scale), w: Math.round(b.width * scale), h: Math.round(b.height * scale) };
}

export function between(text, start, end) {
  const i = text.indexOf(start);
  if (i < 0) return '';
  const j = end ? text.indexOf(end, i + start.length) : -1;
  return text.slice(i, j < 0 ? undefined : j);
}
