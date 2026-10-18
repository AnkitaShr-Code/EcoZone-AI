// Local preview of the deck's slide files: renders each section at 1920x1080 and reports overflow.
import { createRequire } from 'module';
import fs from 'fs';
import path from 'path';
const require = createRequire('/Users/abhi/work/EcoZone-AI/demo-video/package.json');
const { chromium } = require('playwright-core');
const W = '/Users/abhi/work/EcoZone-AI/deck-work';
const deck = JSON.parse(fs.readFileSync(`${W}/root/project/deck.json`, 'utf8'));
const blobs = JSON.parse(fs.readFileSync(`${W}/blobs.json`, 'utf8'));
const only = process.argv.slice(2);
const ids = only.length ? only : deck.order;
const fonts = Object.values(deck.faces).map(f => `<link rel="stylesheet" href="${f.href}">`).join('\n');
let body = '';
for (const id of ids) {
  let html = fs.readFileSync(`${W}/root/project/slides/${id}.html`, 'utf8');
  html = html.replace(/\/_blob\/([0-9a-f]{32})/g, (m, b) => `file://${W}/assets/${blobs[b]}`);
  html = html.replace(/<aside>[\s\S]*?<\/aside>/, '');
  body += `<div class="frame">${html}</div>\n`;
}
const page = `<!doctype html><html><head><meta charset="utf-8">${fonts}<style>
*{margin:0;box-sizing:border-box} body{background:#555}
.frame{width:1920px;height:1080px;overflow:hidden;position:relative}
section{position:relative;width:1920px;height:1080px;overflow:hidden;font-size:32px;line-height:1.4}
p{font-size:inherit} ul,ol{padding-left:1.3em}
h1{font-size:96px;font-weight:600;line-height:1.1} h2{font-size:64px;font-weight:600;line-height:1.15} h3{font-size:44px;font-weight:600;line-height:1.2}
img{display:block} svg{display:block}
table{border-collapse:collapse;width:100%} td,th{border:1px solid #d9d3c6;padding:.35em .6em;text-align:left;vertical-align:top}
section > *:not([style*="position:absolute"]){position:relative}
</style></head><body>${body}</body></html>`;
fs.writeFileSync(`${W}/render/preview.html`, page);
const browser = await chromium.launch({ executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', args: ['--allow-file-access-from-files'] });
const ctx = await browser.newContext({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: Number(process.env.DSF || 1) });
const p = await ctx.newPage();
await p.goto(`file://${W}/render/preview.html`);
await p.evaluate(() => document.fonts.ready);
await p.waitForTimeout(1200);
const frames = await p.$$('.frame');
for (let i = 0; i < frames.length; i++) {
  const id = ids[i];
  await frames[i].screenshot({ path: `${W}/${process.env.OUT || 'render'}/${id}.png` });
  const issues = await frames[i].evaluate((fr) => {
    const out = [];
    const sec = fr.querySelector('section');
    const sr = sec.getBoundingClientRect();
    for (const el of sec.querySelectorAll('h1,h2,h3,p,li,td,th,div,img')) {
      const r = el.getBoundingClientRect();
      if (r.width === 0 && r.height === 0) continue;
      const t = (el.textContent || '').trim().slice(0, 40);
      if (r.right > sr.right + 1 || r.bottom > sr.bottom + 1 || r.left < sr.left - 1 || r.top < sr.top - 1) out.push(`off-canvas ${el.tagName} "${t}" ${Math.round(r.left - sr.left)},${Math.round(r.top - sr.top)} ${Math.round(r.width)}x${Math.round(r.height)}`);
      if (/^(H1|H2|H3|P|LI|TD|TH)$/.test(el.tagName)) {
        if (el.scrollWidth > el.clientWidth + 2) out.push(`h-overflow ${el.tagName} "${t}" ${el.scrollWidth}>${el.clientWidth}`);
        const fs = parseFloat(getComputedStyle(el).fontSize);
        if (fs < 24 && t) out.push(`small-font ${fs}px "${t}"`);
        if (r.bottom > sr.top + 992 && getComputedStyle(el).position !== 'absolute' && t) out.push(`past-992 ${el.tagName} "${t}" bottom=${Math.round(r.bottom - sr.top)}`);
      }
    }
    return out;
  });
  console.log(id, issues.length ? '\n  ' + issues.join('\n  ') : 'ok');
}
await browser.close();
