// Human-looking input for the recording: eased cursor paths, deliberate clicks, slow typing,
// smooth scrolling of the workflow panel. Every wait on the app is a real UI condition.
import fs from 'node:fs';
import path from 'node:path';

export const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const ease = (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);

export function makeActions(page, { stillsDir, failDir, log = console.log }) {
  let cx = 1500, cy = 700; // cursor starts off to the right, on the map
  const a = {};

  a.moveTo = async (x, y, { ms } = {}) => {
    const d = Math.hypot(x - cx, y - cy);
    const dur = ms ?? Math.min(1100, Math.max(280, 250 + d * 0.9));
    const steps = Math.max(8, Math.round(dur / 16));
    const sx = cx, sy = cy;
    // A slight arc looks more like a hand than a ruler.
    const nx = -(y - sy) / (d || 1), ny = (x - sx) / (d || 1), bow = Math.min(40, d * 0.08);
    for (let i = 1; i <= steps; i++) {
      const t = ease(i / steps);
      const arc = Math.sin(Math.PI * t) * bow;
      await page.mouse.move(sx + (x - sx) * t + nx * arc, sy + (y - sy) * t + ny * arc);
      await sleep(dur / steps);
    }
    cx = x; cy = y;
  };

  a.centerOf = async (locator) => {
    const box = await locator.boundingBox();
    if (!box) throw new Error(`No bounding box for ${locator}`);
    return { x: box.x + box.width / 2, y: box.y + box.height / 2, box };
  };

  /** Scroll the element into the middle of its scroll container smoothly, then wait for it to settle. */
  a.reveal = async (locator, block = 'center') => {
    await locator.waitFor({ state: 'visible', timeout: 30000 });
    const moved = await locator.evaluate((el, block) => {
      const r = el.getBoundingClientRect();
      const vh = window.innerHeight;
      const inView = r.top >= 60 && r.bottom <= vh - 20;
      if (inView) return false;
      el.scrollIntoView({ behavior: 'smooth', block });
      return true;
    }, block);
    if (moved) await a.settleScroll(locator);
  };

  a.settleScroll = async (locator) => {
    let last = null;
    for (let i = 0; i < 60; i++) {
      await sleep(60);
      const b = await locator.boundingBox();
      const y = b ? Math.round(b.y) : null;
      if (y === last) return;
      last = y;
    }
  };

  /** Smoothly scroll the workflow panel by dy CSS pixels. */
  a.scrollPanel = async (dy, ms = 700) => {
    await page.evaluate(async ({ dy, ms }) => {
      const el = document.querySelector('aside .overflow-y-auto');
      if (!el) return;
      const y0 = el.scrollTop, t0 = performance.now();
      await new Promise((res) => {
        const step = (now) => {
          const t = Math.min(1, (now - t0) / ms);
          const e = t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;
          el.scrollTop = y0 + dy * e;
          if (t < 1) requestAnimationFrame(step); else res();
        };
        requestAnimationFrame(step);
      });
    }, { dy, ms });
    await sleep(120);
  };

  a.click = async (locator, { pause = 180, reveal = true, offset } = {}) => {
    if (reveal) await a.reveal(locator);
    await locator.waitFor({ state: 'visible', timeout: 30000 });
    const { box } = await a.centerOf(locator);
    const x = box.x + (offset?.x ?? box.width / 2);
    const y = box.y + (offset?.y ?? box.height / 2);
    await a.moveTo(x, y);
    await sleep(pause);
    await page.mouse.down();
    await sleep(90);
    await page.mouse.up();
    await sleep(120);
  };

  a.hover = async (locator, { reveal = true } = {}) => {
    if (reveal) await a.reveal(locator);
    const { x, y } = await a.centerOf(locator);
    await a.moveTo(x, y);
  };

  a.type = async (text, delay = 140) => {
    for (const ch of text) {
      await page.keyboard.type(ch);
      await sleep(delay + Math.random() * 60);
    }
  };

  a.key = async (key, times = 1, gap = 420) => {
    for (let i = 0; i < times; i++) {
      await page.keyboard.press(key);
      await sleep(gap);
    }
  };

  /** Mouse-wheel zoom on the map around a point, in small smooth steps. */
  a.wheelZoom = async (x, y, totalDelta, ms = 3000) => {
    await a.moveTo(x, y);
    const steps = Math.round(ms / 40);
    for (let i = 0; i < steps; i++) {
      await page.mouse.wheel(0, totalDelta / steps);
      await sleep(40);
    }
  };

  a.still = async (name) => {
    const file = path.join(stillsDir, `${name}.png`);
    await page.screenshot({ path: file });
    log(`still ${name}`);
    return file;
  };

  a.fail = async (what, err) => {
    fs.mkdirSync(failDir, { recursive: true });
    const file = path.join(failDir, `fail-${Date.now()}.png`);
    await page.screenshot({ path: file }).catch(() => {});
    throw new Error(`${what}: ${err?.message ?? err} (screenshot ${file})`);
  };

  /** Wait until the map canvas stops changing (tiles, fly-to animations). */
  a.waitMapStill = async (timeout = 15000) => {
    const map = page.locator('.maplibregl-canvas').first();
    const t0 = Date.now();
    let prev = null, same = 0;
    while (Date.now() - t0 < timeout) {
      const buf = await page.screenshot({ clip: { x: 400, y: 60, width: 1180, height: 820 }, type: 'jpeg', quality: 40 });
      if (prev && buf.equals(prev)) { if (++same >= 2) return true; } else same = 0;
      prev = buf;
      await sleep(250);
    }
    log('map did not settle within timeout (continuing)');
    return false;
  };

  return a;
}
