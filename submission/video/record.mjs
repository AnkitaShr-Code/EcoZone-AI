#!/usr/bin/env node
// Records the EcoZone AI demo from the live app with the system Google Chrome.
//
//   node record.mjs [--out takes/<name>] [--until s03] [--no-buildout] [--headed]
//
// Writes into the take directory: frames/ + frames.json (screen capture), markers.json
// (segment start/end in ms from recording start), values.json (numbers and texts read from
// the DOM), stills/ (full-resolution PNGs), console.log. Fails loudly with a screenshot.
import fs from 'node:fs';
import path from 'node:path';
import { execSync } from 'node:child_process';
import { chromium } from 'playwright-core';
import { startRecorder } from './lib/recorder.mjs';
import { makeActions, sleep } from './lib/actions.mjs';
import { parseStats, asideText, boxOf, between } from './lib/read.mjs';

const APP_URL = process.env.ECOZONE_URL ?? 'https://ecozone-451227459430.asia-south1.run.app/';
const args = process.argv.slice(2);
const arg = (k, d) => { const i = args.indexOf(k); return i >= 0 ? args[i + 1] : d; };
const flag = (k) => args.includes(k);
const HERE = path.dirname(new URL(import.meta.url).pathname);
const OUT = path.resolve(HERE, arg('--out', `takes/take-${new Date().toISOString().slice(0, 16).replace(/[:T]/g, '')}`));
const UNTIL = arg('--until', null);
const BUILDOUT = flag('--buildout'); // build-out is cut from the video; record it only on request
const REQUIRE_FIXES = flag('--require-fixes');
const VIEW = { width: 1600, height: 900 }; // CSS px; x1.2 device scale = 1920x1080 frames
const DSF = 1.2;
// Hook target found by probing the settled map's tooltips: a footpath on Apte Path, in sun at 3 pm,
// next to Joshi Hospital and Prayag Hospital. Wheel zoom keeps the point under the cursor fixed.
const HOOK = { x: 1158, y: 644 };

// Do not record on a busy machine: frame timing suffers.
const loadNow = () => Number(execSync('sysctl -n vm.loadavg').toString().replace(/[{}]/g, '').trim().split(/\s+/)[0]);
let load1 = loadNow();
for (let waited = 0; load1 > 8 && !flag('--force'); waited += 10) {
  if (waited >= 300) { console.error(`Load ${load1} > 8 for 5 minutes, not recording. Use --force to override.`); process.exit(2); }
  console.error(`Load ${load1} > 8, waiting...`);
  execSync('sleep 10');
  load1 = loadNow();
}
fs.mkdirSync(path.join(OUT, 'stills'), { recursive: true });
const logFile = fs.createWriteStream(path.join(OUT, 'console.log'));
const T0 = Date.now();
const log = (...m) => { const line = `[${((Date.now() - T0) / 1000).toFixed(1)}s] ${m.join(' ')}`; console.log(line); logFile.write(line + '\n'); };
log(`take ${OUT} load ${load1}`);

const browser = await chromium.launch({
  channel: 'chrome',
  headless: !flag('--headed'),
  // The headless default has no WebGL2; the map needs it. Metal ANGLE uses the real GPU.
  args: ['--use-angle=metal', '--enable-gpu', '--ignore-gpu-blocklist', '--hide-scrollbars', '--font-render-hinting=none'],
});
const context = await browser.newContext({ viewport: VIEW, deviceScaleFactor: DSF, locale: 'en-IN', timezoneId: 'Asia/Kolkata', colorScheme: 'light', reducedMotion: 'no-preference' });
await context.addInitScript({ path: path.join(HERE, 'lib/cursor-init.js') });
const page = await context.newPage();
const consoleErrors = [];
page.on('console', (m) => { if (m.type() === 'error' || m.type() === 'warning') { consoleErrors.push(`${m.type()}: ${m.text().slice(0, 300)}`); logFile.write(`CONSOLE ${m.type()} ${m.text().slice(0, 300)}\n`); } });
page.on('pageerror', (e) => { consoleErrors.push(`pageerror: ${e.message.slice(0, 300)}`); log('PAGEERROR', e.message.slice(0, 200)); });
page.on('dialog', (d) => d.dismiss().catch(() => {}));
page.on('requestfailed', (r) => logFile.write(`REQFAIL ${r.url()} ${r.failure()?.errorText}\n`));
page.on('response', (r) => { if (r.status() >= 400) logFile.write(`HTTP ${r.status()} ${r.url()}\n`); });

const A = makeActions(page, { stillsDir: path.join(OUT, 'stills'), failDir: OUT, log });
const values = { url: APP_URL, recordedAt: new Date().toISOString(), viewport: VIEW, deviceScaleFactor: DSF, boxes: {} };
const markers = [];
let rec = null;
const now = () => (rec ? Math.round(rec.now()) : 0);
let current = null;
const start = (id, title) => { current = { id, title, start: now() }; log(`>> ${id} ${title}`); };
/** Everything after this point in the segment is a hold the editor may shorten. */
const actionsDone = () => { current.actionsEnd = now(); };
const end = (extra = {}) => { Object.assign(current, extra, { end: now() }); if (current.actionsEnd == null) current.actionsEnd = current.end; markers.push(current); log(`<< ${current.id} ${((current.end - current.start) / 1000).toFixed(1)}s`); current = null; };
const hold = (ms) => sleep(ms);
const box = async (name, locator) => {
  try { values.boxes[name] = { ...(await boxOf(locator, DSF)), t: now(), segment: current?.id }; }
  catch (e) { log(`WARN box ${name}: ${e.message.split('\n')[0]}`); }
};
const boxEnd = (name) => { if (values.boxes[name] && values.boxes[name].tEnd == null) values.boxes[name].tEnd = now(); };
const softHover = async (locator) => { try { await A.hover(locator, { reveal: false }); } catch (e) { log(`WARN hover: ${e.message.split('\n')[0]}`); } };
const save = () => {
  fs.writeFileSync(path.join(OUT, 'markers.json'), JSON.stringify({ recordingStartEpoch: rec?.t0 ?? null, segments: markers }, null, 2));
  fs.writeFileSync(path.join(OUT, 'values.json'), JSON.stringify({ ...values, consoleErrors }, null, 2));
};
const stopAt = (id) => UNTIL && id === UNTIL;
const aside = page.locator('aside');
const btn = (name) => page.getByRole('button', { name, exact: true });

async function segFail(e) {
  const file = path.join(OUT, `fail-${current?.id}.png`);
  await page.screenshot({ path: file }).catch(() => {});
  log(`SEGMENT FAILED ${current?.id}: ${e.message.split('\n')[0]} (screenshot ${file})`);
  if (current) current.failed = e.message.split('\n')[0];
  values.failures = [...(values.failures ?? []), { segment: current?.id, error: e.message.split('\n')[0], screenshot: file }];
}

/** Scroll the panel so options A, B, C sit at the bottom of the view and the AI explanation card under
 * them stays below the fold (its text mixes area-level numbers and raw ids; it is not shown in the video). */
async function hideProtectExplanation(group) {
  await group.waitFor();
  for (let i = 0; i < 3; i++) {
    const r = await page.evaluate(() => {
      const g = document.querySelector('[role="radiogroup"][aria-label="Design options"]');
      const card = g?.parentElement?.querySelector(':scope > :not([role="radiogroup"]):last-child') ?? null;
      const after = [...(g?.parentElement?.children ?? [])].find((el) => el !== g && g.compareDocumentPosition(el) & Node.DOCUMENT_POSITION_FOLLOWING);
      const top = (after ?? card)?.getBoundingClientRect().top ?? 99999;
      const gTop = g.getBoundingClientRect().top;
      return { top, gTop, vh: window.innerHeight };
    });
    const need = r.top - (r.vh + 8); // negative: the explanation starts inside the view
    if (need >= -30) { values.protectExplanationHidden = true; return; } // at most its top border shows
    if (need >= 0) { values.protectExplanationHidden = true; return; }
    await A.scrollPanel(need, 350);
  }
  values.protectExplanationHidden = false;
  log('WARN the Protect AI explanation may still be partly in view');
}

async function setLayer(label, on) {
  await page.getByRole('button', { name: /^Layers/ }).click();
  const sw = page.getByRole('switch', { name: new RegExp(`^${label}`) });
  if ((await sw.getAttribute('aria-checked')) !== String(on)) await sw.click();
  await page.keyboard.press('Escape');
}

async function main() {
  // ---------- load (not recorded) ----------
  await page.goto(APP_URL, { waitUntil: 'load' });
  await btn('Use this area').waitFor({ timeout: 60000 });
  await A.waitMapStill();
  const missingWorker = consoleErrors.some((e) => e.includes('Worker failed to load'));
  values.app = { basemapWorkerMissing: missingWorker };
  if (missingWorker) log('NOTE: MapLibre worker failed to load: the basemap (streets, labels) does not draw on the live app.');
  if (missingWorker && REQUIRE_FIXES) await A.fail('preflight', 'basemap worker still missing on the live app (PR #41 not deployed?)');
  if (REQUIRE_FIXES) {
    // The rejected options come with the sites layer (PR #39): check before spending a live search.
    const sites = await page.evaluate(async () => (await fetch('/api/areas/deccan/sites')).json());
    const refused = sites.filter((x) => x.singleSite?.ventilation?.ok === false).length;
    values.app.refusedSites = refused;
    log(`preflight: ${sites.length} sites, ${refused} refused by the ventilation check`);
    if (!refused) log('WARN preflight: /sites marks no site as refused; the plan may show no rejected options (PR #39 not deployed?)');
  }
  // Start with the priority fill off so the hook shows footpaths, buildings and shadows; s02 turns it on.
  await setLayer('Priority', false);
  await A.waitMapStill();
  await page.mouse.move(1500, 700);

  rec = await startRecorder(page, OUT);
  await hold(600);

  // ---------- s01 hook: zoom toward waiting points, footpaths in sun at 3 pm ----------
  start('s01', 'Hook: footpaths in the afternoon sun');
  {
    const t = await asideText(page);
    values.area = {
      name: (t.match(/\n(Deccan[^\n]+)\n/) ?? [])[1] ?? null,
      counts: (t.match(/(\d+) blocks · (\d+) buildings · (\d+) waiting points/) ?? []).slice(1).map(Number),
      baseline: parseStats(between(t, 'Area cooling score', 'Top hotspots')),
      defaultHeights: (t.match(/(\d+) of (\d+) buildings use a default height/) ?? []).slice(1).map(Number),
    };
    values.shadeTimeAtStart = await page.getByRole('radio', { name: '3 pm' }).getAttribute('aria-checked');
    await A.moveTo(HOOK.x, HOOK.y, { ms: 1400 });
    await A.wheelZoom(HOOK.x, HOOK.y, -600, 4500);
    await A.waitMapStill(6000);
    // The cursor sits on a sunny footpath: nudge it so the app's own tooltip appears.
    await A.moveTo(HOOK.x + 1, HOOK.y, { ms: 100 });
    await hold(600);
    values.hookTooltip = await page.evaluate(() => {
      const vis = [...document.querySelectorAll('.deck-tooltip')].find((e) => e.style.display !== 'none' && e.innerText.trim());
      return vis ? vis.innerText.trim() : null;
    });
    if (!/in sun at 3 pm/.test(values.hookTooltip ?? '')) log(`WARN hook tooltip is not a sunny footpath: ${values.hookTooltip}`);
    log(`hook tooltip: ${values.hookTooltip}`);
    actionsDone();
    await A.still('01-hook-3pm');
    await hold(3500);
  }
  end();

  // ---------- s02 priority map, shade times, hotspot ----------
  start('s02', 'Repair: priority map and hotspots, shade at 3 pm');
  {
    await A.click(page.getByRole('button', { name: /^Layers/ }), { reveal: false });
    await hold(500);
    await A.click(page.getByRole('switch', { name: /^Priority/ }), { reveal: false });
    await hold(900);
    await page.keyboard.press('Escape');
    await A.waitMapStill(3000);
    await hold(800);
    for (const t of ['1 pm', '4 pm', '3 pm']) {
      await A.click(page.getByRole('radio', { name: t }), { reveal: false });
      await hold(850);
    }
    await box('shadeTimes', page.getByRole('radiogroup', { name: 'Shade time' }));
    await box('areaStats', page.locator('aside div.grid:visible').filter({ hasText: 'Area cooling score' }).first());
    const t = await asideText(page);
    values.hotspots = [...between(t, 'Top hotspots', 'Use this area').matchAll(/(\d)\n(Block \d+) · ([^\n]+)\n([^\n]+)/g)].map((m) => ({ rank: Number(m[1]), block: m[2], priority: m[3], drivers: m[4] }));
    await softHover(page.locator('aside div.grid:visible').filter({ hasText: 'Area cooling score' }).first());
    await hold(700);
    boxEnd('areaStats');
    await A.click(page.getByRole('button', { name: /^1 Block \d+/ }));
    await A.waitMapStill(5000);
    const sel = await page.locator('section[aria-label="Selected on map"]').innerText().catch(() => '');
    values.hotspotSelected = { text: sel, stats: parseStats(sel) };
    await box('selectionCard', page.locator('section[aria-label="Selected on map"]'));
    actionsDone();
    await A.still('02-priority-map-3pm');
    await hold(2500);
  }
  end();
  if (stopAt('s02')) return;

  // ---------- s03 budget ----------
  start('s03', 'Repair: budget 10 lakh, 30% helps this summer');
  {
    await page.keyboard.press('Escape');
    await A.click(btn('Use this area'));
    const budget = page.locator('#budget');
    await budget.waitFor();
    await A.click(budget);
    await page.keyboard.press('ControlOrMeta+a');
    await A.type('10');
    await hold(500);
    const thumb = page.getByRole('slider', { name: 'Share of the budget that helps this summer' });
    await A.click(thumb);
    await A.key('ArrowRight', 2, 520);
    await hold(400);
    const t = await asideText(page);
    values.budget = {
      lakh: Number(await budget.inputValue()),
      quickWinText: (t.match(/at least (\d+)% of the budget/) ?? [])[0] ?? null,
      quickWinPct: Number((t.match(/at least (\d+)% of the budget/) ?? [])[1]),
    };
    if (values.budget.lakh !== 10 || values.budget.quickWinPct !== 30) await A.fail('budget inputs', JSON.stringify(values.budget));
    await box('budgetStep', page.locator('section[aria-current="step"]'));
    await A.hover(btn('Draft cooling plan'));
    actionsDone();
    await hold(800);
  }
  end();
  if (stopAt('s03')) return;

  // ---------- s04 search (time-lapsed in the edit) ----------
  start('s04', 'Repair: Gemini proposes, the engine scores');
  {
    await A.click(btn('Draft cooling plan'));
    const t0 = Date.now();
    let midShot = false;
    const statuses = [];
    while (true) {
      const t = await asideText(page);
      const status = (t.match(/(Preparing the search…|Round \d of up to 2 · \d+ options scored|Search finished · \d+ options scored in \d rounds)/) ?? [])[0];
      if (status && statuses.at(-1)?.status !== status) { statuses.push({ status, ms: now() }); log(`search: ${status}`); }
      if (!midShot && /Round 2 of up to 2 · [1-9]/.test(t)) { midShot = true; await A.still('03-search-mid-run'); await box('searchProgress', page.locator('[aria-live="polite"]').first().locator('xpath=ancestor::div[contains(@class,"rounded-lg")][1]')); }
      if (/The search stopped with an error/.test(t)) await A.fail('repair search', 'The search stopped with an error');
      if (/AI plan beat the simple baseline|The simple baseline won|Search stopped early/.test(t)) break;
      if (Date.now() - t0 > 300000) await A.fail('repair search', 'timeout 300 s');
      if (!midShot && Date.now() - t0 > 20000 && Date.now() - t0 < 21500) await A.moveTo(260, 470, { ms: 1200 });
      await sleep(400);
    }
    values.search = { seconds: Math.round((Date.now() - t0) / 100) / 10, statuses };
    log(`search finished in ${values.search.seconds}s`);
    actionsDone();
  }
  end();

  // ---------- s05 plan ----------
  start('s05', 'Repair: the plan and its scores');
  try {
    await sleep(800);
    const t = await asideText(page);
    const all = await page.locator('aside').evaluate((el) => el.textContent);
    const summary = (t.match(/(AI plan beat the simple baseline|The simple baseline won|Search stopped early)[^\n]*/) ?? [])[0];
    const progressAll = (all.match(/Search finished · (\d+) options scored in (\d) rounds/) ?? []);
    values.repair = {
      verdict: summary?.startsWith('AI plan beat') ? 'gemini' : summary?.startsWith('The simple baseline won') ? 'greedy' : 'stopped',
      verdictText: summary?.replace(/\. Show search details$/, '') ?? null,
      candidates: Number(progressAll[1] ?? NaN), rounds: Number(progressAll[2] ?? NaN),
      baselineScore: Number((all.match(/Baseline: best gain per rupee(\d+(?:\.\d+)?)/) ?? [])[1] ?? NaN),
      stats: parseStats(between(t, 'Area cooling score', 'Cost')),
      cost: (t.match(/Cost\n([^\n]+)/) ?? [])[1] ?? null,
      quickWins: (t.match(/Helps this summer\n([^\n]+)/) ?? [])[1] ?? null,
      ventilation: (t.match(/Ventilation check\n([^\n]+)/) ?? [])[1] ?? null,
      waitPointsShaded: Number((t.match(/Waiting points shaded\n(\d+)/) ?? [])[1] ?? NaN),
      interventions: Number((t.match(/Interventions \((\d+)\)/) ?? [])[1] ?? NaN),
      groups: [...t.matchAll(/\n([A-Z][a-z ]+?) · (\d+) of (\d+)\n(₹ [^\n]+)/g)].map((m) => ({ type: m[1], on: Number(m[2]), of: Number(m[3]), subtotal: m[4] })),
      explanationSource: (t.match(/(Explanation from engine values|Explained by AI[^\n]*)/) ?? [])[0] ?? null,
      explanation: between(t, (t.match(/(Explanation from engine values|Explained by AI[^\n]*)/) ?? [''])[0], 'Interventions (').split('\n').slice(1).filter(Boolean),
      rejected: [],
    };
    // Gemini candidate scores from the progress list (the details element holds them even when closed).
    values.repair.candidateScores = await page.locator('aside ol li li').evaluateAll((lis) => lis.map((li) => li.textContent.trim()));
    log(`verdict ${values.repair.verdict}; ACS ${JSON.stringify(values.repair.stats['Area cooling score'])}`);
    await box('verdict', page.locator('aside summary').filter({ hasText: /baseline|stopped/ }).first());
    await box('planStats', page.locator('aside div.grid:visible').filter({ hasText: 'Area cooling score' }).first());
    await A.hover(page.locator('aside summary').filter({ hasText: /baseline|stopped/ }).first(), { reveal: false });
    await hold(1500);
    await softHover(page.locator('aside div.grid:visible').filter({ hasText: 'Area cooling score' }).first());
    await hold(1500);
    await A.hover(page.getByText('Waiting points shaded'), { reveal: false });
    await box('planFacts', page.getByText('Waiting points shaded').locator('xpath=ancestor::dl[1]'));
    await hold(1500);
    await A.still('04-plan-scores');
    // Show the mix of interventions.
    const list = page.locator('[aria-label="Interventions in the plan"]');
    boxEnd('verdict'); boxEnd('planStats'); boxEnd('planFacts');
    await A.reveal(list, 'start');
    await A.scrollPanel(-60, 400);
    await A.hover(list.locator('summary').first(), { reveal: false });
    await box('planList', list);
    await hold(1200);
    // Lead into the shade view: tidy the list, open the tree rows, click one that shades a waiting point.
    boxEnd('planList');
    const groups = page.locator('[aria-label="Interventions in the plan"] details');
    for (let i = 0; i < (await groups.count()); i++) {
      const g = groups.nth(i);
      const isTree = /Street tree rows/.test(await g.locator('summary').innerText());
      if (!isTree && (await g.evaluate((d) => d.open))) { await A.click(g.locator('summary')); await hold(300); }
    }
    let target = null;
    const order = [];
    for (let i = 0; i < (await groups.count()); i++) order[/Street tree rows/.test(await groups.nth(i).locator('summary').innerText()) ? 'unshift' : 'push'](i);
    for (const i of order) {
      const g = groups.nth(i);
      const rows = g.locator('li').filter({ hasText: 'Shades a waiting point' });
      if (await rows.count()) {
        if (!(await g.evaluate((d) => d.open))) { await A.click(g.locator('summary')); await hold(400); }
        target = rows.first();
        break;
      }
    }
    if (!target) target = page.locator('[aria-label="Interventions in the plan"] li').first();
    const link = target.locator('button:not([role="checkbox"])').first();
    values.shadeSite = { name: await link.innerText(), detail: await target.locator('p').first().innerText() };
    log(`shade site: ${values.shadeSite.name} (${values.shadeSite.detail})`);
    await A.click(link);
    await A.waitMapStill(5000);
    values.shadeSite.card = await page.locator('section[aria-label="Selected on map"]').innerText().catch(() => null);
    await softHover(page.locator('section[aria-label="Selected on map"] h3'));
    // Rejected options, if the live app shows any.
    const rejected = page.locator('section[aria-label="Rejected options"]');
    if (await rejected.count()) {
      values.repair.rejected = await rejected.locator('li').evaluateAll((lis) => lis.map((li) => li.innerText));
    }
    actionsDone();
    await hold(1500);
  } catch (e) { await segFail(e); }
  end();

  // ---------- s06 rejected tree row (only if the app shows one) ----------
  const rejected = page.locator('section[aria-label="Rejected options"]');
  if (await rejected.count()) {
    start('s06', 'Repair: a tree row rejected for ventilation');
    await A.reveal(rejected);
    await box('rejected', rejected);
    values.repair.rejected = await rejected.locator('li').evaluateAll((lis) => lis.map((li) => li.innerText));
    await softHover(rejected.locator('li p').first());
    await A.still('05-rejected-tree-row');
    actionsDone();
    await hold(2500);
    end();
  } else {
    log('NOTE: no rejected options in the plan panel (section "Rejected by the ventilation check" absent).');
  }

  // ---------- s07 shade today vs with plan ----------
  start('s07', 'Repair: shade at 3 pm, today and with the plan');
  try {
    await page.keyboard.press('Escape'); // keep the map clean; the flight is done
    // Priority fill off, so footpath shade reads clearly.
    await A.click(page.getByRole('button', { name: /^Layers/ }), { reveal: false });
    await hold(300);
    await A.click(page.getByRole('switch', { name: /^Priority/ }), { reveal: false });
    await hold(400);
    await page.keyboard.press('Escape');
    const toggle = page.getByRole('radiogroup', { name: 'Map shows' });
    await box('mapToggle', toggle);
    await A.click(page.getByRole('radio', { name: 'Today' }), { reveal: false });
    await A.waitMapStill(3000);
    await hold(1100);
    await A.still('06a-shade-3pm-today');
    await A.click(page.getByRole('radio', { name: 'With plan' }), { reveal: false });
    values.marks = { ...(values.marks ?? {}), withPlan: now() };
    await A.waitMapStill(3000);
    await hold(600);
    await A.still('06b-shade-3pm-with-plan');
    actionsDone();
    await hold(1800);
  } catch (e) { await segFail(e); }
  end();

  // ---------- s08 accept and brief ----------
  start('s08', 'Repair: accept the plan, export the brief');
  try {
    await A.click(btn('Accept plan'));
    await btn('Download brief').waitFor();
    await A.click(btn('Download brief')); // window.print(); the printable brief is the print view
    await hold(400);
    await page.emulateMedia({ media: 'print' });
    await page.addStyleTag({ content: '@media print { #print-root { zoom: 1.4 } }' });
    await sleep(400);
    const brief = await page.locator('#print-root').innerText();
    values.brief = {
      title: brief.split('\n').find((l) => l.startsWith('Cooling plan')) ?? null,
      subtitle: brief.split('\n').find((l) => l.startsWith('Budget')) ?? null,
      sections: [...brief.matchAll(/\n(Outcome|Before [^\n]+|In the [^\n]+|Plant with [^\n]+|Field checks[^\n]*|Rejected options)\n/g)].map((m) => m[1]),
      outcome: parseStats(brief.replace(/\t/g, '\n')),
    };
    actionsDone();
    await A.still('07-brief');
    await hold(1600);
    // Scroll the brief slowly to the phases and field checks.
    for (let i = 0; i < 24; i++) { await page.mouse.wheel(0, 30); await sleep(40); }
    await hold(1500);
    await page.emulateMedia({ media: 'screen' });
    await hold(300);
  } catch (e) { await segFail(e); }
  end();
  if (stopAt('s08')) return;

  // ---------- s09 protect: the parcel ----------
  start('s09', 'Protect: a vacant 3,988 m2 plot on an 8 m street');
  try {
    await A.click(page.getByRole('radio', { name: 'Protect' }), { reveal: false });
    await page.locator('[aria-label="Vacant parcels"]').waitFor();
    await A.waitMapStill(5000);
    const PARCEL = process.env.PARCEL_TEXT ?? '3,988.1 m²'; // the demo parcel pc_004 (FIRST: first in the list, for mock tests)
    const item = PARCEL === 'FIRST' ? page.locator('[aria-label="Vacant parcels"] button').first() : page.locator('[aria-label="Vacant parcels"] button').filter({ hasText: PARCEL });
    if ((await item.count()) !== 1) await A.fail('parcel', `expected one 3,988.1 m² parcel, found ${await item.count()}`);
    await A.click(item);
    await A.waitMapStill(5000);
    const sel = await page.locator('section[aria-label="Selected on map"]').innerText();
    values.parcel = { listText: await item.innerText(), selected: sel };
    await A.reveal(page.locator('section[aria-label="Selected on map"]'), 'start');
    await A.hover(page.locator('section[aria-label="Selected on map"] p').last(), { reveal: false });
    actionsDone();
    await hold(1800);
  } catch (e) { await segFail(e); }
  end();

  // ---------- s10 proposal and live risk ----------
  start('s10', 'Protect: a large proposal, live scores and risk label');
  try {
    await A.click(btn('Use this parcel'));
    const height = page.getByRole('slider', { name: 'Height' });
    await height.waitFor();
    await page.locator('section[aria-label="Impact on the parcel\'s block"]').getByText(/risk/).first().waitFor({ timeout: 30000 });
    const impact = page.locator('section[aria-label="Impact on the parcel\'s block"]');
    // Keep the sliders and the impact section on screen together.
    await A.reveal(page.getByText('Describe proposal'), 'start');
    await hold(600);
    const readImpact = async () => {
      const t = await impact.innerText();
      return { risk: (t.match(/(Low|Moderate|High) risk/) ?? [])[1] ?? null, riskText: t.split('\n').slice(1, 3).join(' ').replace(/\s+/g, ' ').trim(), stats: parseStats(t), blocksWorse: (t.match(/(\d+) existing blocks? around the parcel lose cooling score/) ?? [])[1] ?? null };
    };
    values.proposalDefault = { design: await page.locator('section[aria-current="step"]').innerText().then((t) => ({ height: (t.match(/Height\n([^\n]+)/) ?? [])[1], footprint: (t.match(/Footprint\n([^\n]+)/) ?? [])[1], green: (t.match(/Green or open space\n([^\n]+)/) ?? [])[1], orientation: (t.match(/Orientation of the long side\n([^\n]+)/) ?? [])[1] })), impact: await readImpact() };
    await A.click(height);
    const steps = Number(process.env.EXTRA_FLOORS ?? 3);
    for (let i = 0; i < steps; i++) { await page.keyboard.press('ArrowRight'); await sleep(900); }
    await sleep(800);
    const t = await page.locator('section[aria-current="step"]').innerText();
    values.proposal = {
      design: { height: (t.match(/Height\n([^\n]+)/) ?? [])[1], footprint: (t.match(/Footprint\n([^\n]+)/) ?? [])[1], green: (t.match(/Green or open space\n([^\n]+)/) ?? [])[1], orientation: (t.match(/Orientation of the long side\n([^\n]+)/) ?? [])[1] },
      impact: await readImpact(),
    };
    log(`proposal ${JSON.stringify(values.proposal)}`);
    await box('riskBadge', impact.locator('span').filter({ hasText: /risk/ }).first());
    await box('impact', impact);
    await A.hover(impact.locator('span').filter({ hasText: /risk/ }).first(), { reveal: false });
    actionsDone();
    await A.still('08-protect-proposal-risk');
    await hold(2500);
  } catch (e) { await segFail(e); }
  end();

  // ---------- s11 design search and options A, B, C ----------
  start('s11', 'Protect: Gemini searches, options A, B, C');
  try {
    await A.click(btn('Find better designs'));
    const t0 = Date.now();
    const statuses = [];
    while (true) {
      const t = await asideText(page);
      const status = (t.match(/(Preparing the search…|Round \d of up to 2 · \d+ options scored|Search finished · \d+ options scored in \d rounds)/) ?? [])[0];
      if (status && statuses.at(-1)?.status !== status) { statuses.push({ status, ms: now() }); log(`protect search: ${status}`); }
      if (/The search stopped with an error/.test(t)) await A.fail('protect search', 'The search stopped with an error');
      if (await page.getByRole('radiogroup', { name: 'Design options' }).count()) break;
      if (Date.now() - t0 > 300000) await A.fail('protect search', 'timeout 300 s');
      await sleep(400);
    }
    values.protectSearch = { seconds: Math.round((Date.now() - t0) / 100) / 10, statuses };
    const group = page.getByRole('radiogroup', { name: 'Design options' });
    await hideProtectExplanation(group);
    current.searchEnd = now();
    const opts = await group.getByRole('radio').evaluateAll((els) => els.map((e) => e.innerText));
    values.options = opts.map((o) => {
      const lines = o.split('\n').map((l) => l.trim()).filter(Boolean);
      const head = lines[0].match(/Option ([ABC]) · (.+)/) ?? [];
      const riskLine = lines.find((l) => /risk$/.test(l));
      const worst = lines.find((l) => /worst change/.test(l));
      const trade = lines.at(-1);
      return { key: head[1], title: head[2], design: lines[1], risk: riskLine?.replace(' risk', '') ?? null, worst: worst ?? null, worstValue: Number((worst?.match(/worst change (\d+(?:\.\d+)?)/) ?? [])[1] ?? NaN), worstIndex: (worst?.match(/on (\w[\w ]*)$/) ?? [])[1] ?? null, tradeOff: trade, floorAreaPct: Number((trade.match(/(\d+)% of the floor area/) ?? [])[1] ?? (trade.startsWith('All the proposed') ? 100 : NaN)) };
    });
    const expl = await page.locator('section[aria-current="step"]').innerText();
    values.protectExplanationSource = (expl.match(/(Explanation from engine values|Explained by AI[^\n]*)/) ?? [])[0] ?? null;
    log(`options ${JSON.stringify(values.options)}`);
    await box('options', group);
    for (const k of ['A', 'B', 'C']) {
      await A.hover(group.getByRole('radio', { name: new RegExp(`Option ${k}`) }), { reveal: false });
      await hold(1300);
    }
    await A.click(group.getByRole('radio', { name: /Option B/ }), { reveal: false });
    await A.waitMapStill(4000);
    actionsDone();
    await A.still('09-protect-options-abc');
    await hold(2500);
  } catch (e) { await segFail(e); }
  end();
  if (stopAt('s11')) return;

  // ---------- s12 build-out (optional in the cut) ----------
  if (BUILDOUT) {
    start('s12', 'Protect: build-out on nearby parcels');
    await A.click(btn('Use this design'));
    await btn('Run build-out').waitFor();
    await A.click(btn('Run build-out'));
    const sec = page.locator('section[aria-current="step"]');
    await sec.getByText('Whole area, today and built out').waitFor({ timeout: 30000 });
    await sec.getByText(/parcels? at high risk/).waitFor({ timeout: 30000 });
    await A.waitMapStill(6000);
    const t = await sec.innerText();
    values.buildout = { text: between(t, 'Envelope', 'Continue to brief'), stats: parseStats(t), summary: (t.match(/\d+ parcels? at high risk[^\n]+/) ?? [])[0] ?? null, parcels: (t.match(/(\d+) vacant parcels? including this one/) ?? [])[1] ?? null };
    log(`buildout ${JSON.stringify(values.buildout.stats)} ${values.buildout.summary}`);
    await A.reveal(sec.getByText('Whole area, today and built out'));
    actionsDone();
    await A.still('10-protect-buildout');
    await hold(2500);
    end();
  }
}

try {
  await main();
} catch (e) {
  log('FAILED', e.message);
  if (current) end({ failed: true });
  process.exitCode = 1;
} finally {
  if (rec) { const r = await rec.stop(); log(`frames ${r.count}`); }
  save();
  await context.close().catch(() => {});
  await browser.close().catch(() => {});
  log('done');
  logFile.end();
}
