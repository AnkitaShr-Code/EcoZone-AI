// Deterministic rendering of the HTML/CSS overlays to transparent PNG sequences at 30 fps.
// Every CSS animation is paused and stepped to each frame time; frames where nothing is
// animating are copied from the previous frame instead of re-rendered.
import fs from 'node:fs';
import path from 'node:path';
import { createHash } from 'node:crypto';
import { chromium } from 'playwright-core';

const HERE = path.dirname(new URL(import.meta.url).pathname);
const GFX = path.resolve(HERE, '../graphics');
export const FPS = 30;

let browser = null;
export async function gfxBrowser() {
  browser ??= await chromium.launch({ channel: 'chrome', headless: true, args: ['--hide-scrollbars', '--force-color-profile=srgb'] });
  return browser;
}
export async function closeGfx() { await browser?.close(); browser = null; }

/** Render graphics/<name>.html with params for `dur` seconds into a cached directory. Returns { dir, frames }. */
export async function renderGraphic(name, params, dur, cacheRoot) {
  const p = { ...params, dur };
  const key = createHash('sha1').update(JSON.stringify([name, p, fs.readFileSync(path.join(GFX, `${name}.html`), 'utf8'), fs.readFileSync(path.join(GFX, 'base.css'), 'utf8')])).digest('hex').slice(0, 12);
  const dir = path.join(cacheRoot, `${name}-${key}`);
  const frames = Math.max(1, Math.round(dur * FPS));
  if (fs.existsSync(path.join(dir, 'done'))) return { dir, frames };
  fs.rmSync(dir, { recursive: true, force: true });
  fs.mkdirSync(dir, { recursive: true });
  const b = await gfxBrowser();
  const page = await b.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
  await page.goto(`file://${path.join(GFX, `${name}.html`)}#${encodeURIComponent(JSON.stringify(p))}`);
  await page.waitForFunction(() => window.READY === true);
  await page.evaluate(() => document.getAnimations().forEach((a) => a.pause()));
  let prev = null;
  for (let i = 0; i < frames; i++) {
    const ms = (i * 1000) / FPS;
    const active = await page.evaluate((ms) => {
      let any = false;
      for (const a of document.getAnimations()) {
        a.currentTime = ms;
        const t = a.effect.getComputedTiming();
        if (t.progress !== null && (t.activeDuration === Infinity || (ms >= (t.delay ?? 0) - 40 && ms <= (t.delay ?? 0) + t.activeDuration + 40))) any = true;
      }
      if (typeof window.frame === 'function') { window.frame(ms); any = true; }
      return any;
    }, ms);
    const file = path.join(dir, `${String(i).padStart(5, '0')}.png`);
    if (!active && prev) fs.copyFileSync(prev, file);
    else await page.screenshot({ path: file, omitBackground: true });
    prev = file;
  }
  await page.close();
  fs.writeFileSync(path.join(dir, 'done'), '');
  return { dir, frames };
}

// CLI: node tools/gfx.mjs <name> '<json params>' <seconds> -> renders and writes a preview PNG at 2 s.
if (process.argv[1] === new URL(import.meta.url).pathname) {
  const [name, json, secs] = process.argv.slice(2);
  const r = await renderGraphic(name, JSON.parse(json ?? '{}'), Number(secs ?? 4), path.resolve(HERE, '../build/gfx'));
  console.log(r);
  await closeGfx();
}
