#!/usr/bin/env node
// Fill the narration and overlay templates in script.json from a take's values.json and from
// evals/REPORT.md. No number is typed by hand: every one is read from the take or the report.
//
//   node tools/fill.mjs <takeDir>   -> <takeDir>/filled.json, narration-segments.json, narration.md
import fs from 'node:fs';
import path from 'node:path';

const HERE = path.dirname(new URL(import.meta.url).pathname);
const ROOT = path.resolve(HERE, '..');
const REPO = path.resolve(ROOT, '..');

export function reportFacts() {
  const r = fs.readFileSync(path.join(REPO, 'evals/REPORT.md'), 'utf8');
  const pass = r.match(/\*\*Results by outcome:\*\* (\d+) pass \((\d+) evals\)/);
  const live = r.split('### Live Gemini')[1]?.split('###')[0] ?? '';
  const outcomes = [...live.matchAll(/^\| `([\w]+)` \|.*?\| (win|loss|tie) \|/gm)].map((m) => ({ case: m[1], outcome: m[2] }));
  const heat = r.match(/\| HEI \| test \(held out, headline\) \| (\d+) of \d+ \| ([+-]\d\.\d+) \| (\d\.\d+) \|/);
  const count = (o) => outcomes.filter((x) => x.outcome === o).length;
  return {
    evalsPass: Number(pass[1]), evalsTotal: Number(pass[2]),
    gemini: { cases: outcomes.length, wins: count('win'), losses: count('loss'), ties: count('tie'), outcomes },
    heat: { blocks: Number(heat[1]), rho: heat[2], p: heat[3] },
  };
}

const num = (s) => Number(String(s).replace(/[^\d.]/g, ''));
const words = ['zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten'];
const word = (n) => words[n] ?? String(n);
const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1);

export function derive(v, take) {
  const st = (o, k) => o?.[k];
  const acs = v.repair?.stats?.['Area cooling score'];
  const opt = Object.fromEntries((v.options ?? []).map((o) => [o.key, o]));
  const impact = v.proposal?.impact ?? {};
  const worst = (impact.riskText ?? '').match(/worst change (\d+(?:\.\d+)?) on (\w[\w ]*)/);
  const vci = impact.stats?.Ventilation;
  const parcelM = (v.parcel?.listText ?? '').match(/([\d,]+(?:\.\d+)?) m² · street (\d+) m wide/);
  const R = reportFacts();
  const d = {
    hook: { tooltipLine: (v.hookTooltip ?? '').split('\n').join(' · ') },
    area: {
      acs: st(v.area?.baseline?.['Area cooling score'], 'value'), pss: st(v.area?.baseline?.['Footpath shade'], 'value'),
      hei: st(v.area?.baseline?.['Heat exposure'], 'value'), gcs: st(v.area?.baseline?.['Green connectivity'], 'value'),
    },
    budget: { lakh: v.budget?.lakh, quickWinPct: v.budget?.quickWinPct },
    search: { seconds: Math.round(v.search?.seconds ?? 0) },
    protectSearch: { seconds: Math.round(v.protectSearch?.seconds ?? 0) },
    repair: {
      verdict: v.repair?.verdict, verdictText: v.repair?.verdictText,
      acsAfter: acs?.value, acsBefore: acs ? acs.value - (acs.delta ?? 0) : null,
      costLakh: (v.repair?.cost ?? '').match(/₹ ([\d.]+) lakh/)?.[1] ?? null,
      quickWinLakh: (v.repair?.quickWins ?? '').match(/₹ ([\d.]+) lakh/)?.[1] ?? null,
      waitPointsShaded: v.repair?.waitPointsShaded,
      ventilation: v.repair?.ventilation,
    },
    parcel: { areaText: parcelM ? `${parcelM[1]} m²` : null, areaSpoken: parcelM ? parcelM[1].replace(/\.\d+$/, '') : null, streetM: parcelM ? Number(parcelM[2]) : null },
    proposal: {
      floors: num(v.proposal?.design?.height ?? ''), footprintPct: num(v.proposal?.design?.footprint ?? ''),
      riskWord: (impact.risk ?? '').toLowerCase(), worst: worst ? Number(worst[1]) : null, worstIndex: worst?.[2] ?? null,
      vciDrop: vci?.delta != null ? Math.abs(vci.delta) : null,
    },
    A: opt.A ?? {}, B: { ...(opt.B ?? {}), worst: opt.B?.worstValue }, C: { ...(opt.C ?? {}), worst: opt.C?.worstValue },
    report: R,
    mix: mixPhrase(v.repair?.groups ?? []),
    beatWord: edged(v) ? 'edged out' : 'beat',
    rejectedShown: (v.repair?.rejected ?? []).length > 0,
  };
  d.A.worst = opt.A?.worstValue;
  return d;
}

/** "31 street tree rows, 3 cool roof blocks and 1 depave and plant site", largest group first. */
function mixPhrase(groups) {
  const parts = [...groups].filter((g) => g.on > 0).sort((a, b) => b.on - a.on).map((g) => {
    let t = g.type.toLowerCase();
    if (g.on === 1) t = t.replace(/^(\w[\w ]*?)s\b/, '$1').replace('rows', 'row').replace('sites', 'site').replace('blocks', 'block').replace('greens', 'green').replace('structures', 'structure');
    return `${g.on} ${t}`;
  });
  return parts.length > 1 ? `${parts.slice(0, -1).join(', ')} and ${parts.at(-1)}` : parts[0] ?? '';
}
/** True when the AI plan won but shows the same rounded score as the baseline in the search list. */
function edged(v) {
  const base = v.repair?.baselineScore;
  const best = Math.max(...(v.repair?.candidateScores ?? []).filter((c) => !/Over budget|needs|Below/.test(c)).map((c) => Number((c.match(/(\d+(?:\.\d+)?)$/) ?? [])[1] ?? NaN)).filter((x) => !Number.isNaN(x)));
  return v.repair?.verdict === 'gemini' && Number.isFinite(best) && best === base;
}

function get(obj, p) { return p.split('.').reduce((o, k) => (o == null ? undefined : o[k]), obj); }
export function fillText(tpl, d, missing) {
  return tpl.replace(/\{\{([\w.]+)\}\}/g, (_, p) => {
    const val = get(d, p);
    if (val === undefined || val === null || val === '' || Number.isNaN(val)) { missing.push(p); return `{{${p}}}`; }
    return String(val);
  });
}

export function fill(takeDir) {
  const script = JSON.parse(fs.readFileSync(path.join(ROOT, 'script.json'), 'utf8'));
  const markers = JSON.parse(fs.readFileSync(path.join(takeDir, 'markers.json'), 'utf8'));
  const v = JSON.parse(fs.readFileSync(path.join(takeDir, 'values.json'), 'utf8'));
  const d = derive(v, takeDir);
  const have = new Set(markers.segments.map((s) => s.id));
  const missing = [];
  const out = [];
  for (const seg of script.segments) {
    if (seg.include === false) continue;
    if (seg.source !== 'graphic' && !have.has(seg.id)) continue; // e.g. s06 when the app shows no rejected option
    const vars = {};
    for (const [k, alt] of Object.entries(seg.vars ?? {})) vars[k] = d.rejectedShown && have.has('s06') ? alt.ifShown : alt.ifAbsent;
    const ctx = { ...d, ...vars };
    let tpl = seg.narration ?? seg.variants?.[d.repair.verdict] ?? seg.variants?.greedy;
    // Protect: say "ventilation ... falls by" only when the worst change really is ventilation.
    if (seg.id === 's10' && d.proposal.worstIndex !== 'ventilation') {
      tpl = tpl.replace("ventilation on the parcel's own block falls by {{proposal.vciDrop}} points", "the worst change on the parcel's own block is {{proposal.worst}} points, on {{proposal.worstIndex}}");
    }
    // Protect: describe option C against B exactly as the numbers fall in this take.
    if (seg.id === 's11' && d.C.worst != null && d.B.worst != null) {
      const cPart = d.C.worst < d.B.worst ? 'Option C keeps {{C.floorAreaPct}} percent and cuts it to {{C.worst}}.'
        : d.C.worst === d.B.worst ? 'Option C keeps {{C.floorAreaPct}} percent, with the same worst change.'
          : 'Option C keeps {{C.floorAreaPct}} percent, with a worst change of {{C.worst}}.';
      tpl = tpl.replace('Option C keeps {{C.floorAreaPct}} percent, at {{C.worst}}.', cPart);
    }
    // The shade view: talk about trees only when the selected site is a tree row.
    if (seg.id === 's07' && !/Street tree row/.test(v.shadeSite?.card ?? 'Street tree row')) {
      tpl = tpl.replace('Once the new trees grow, this footpath', 'With the plan, this footpath');
    }
    const text = fillText(tpl, ctx, missing);
    const lowerThird = seg.lowerThird ? { ...seg.lowerThird, text: fillText(seg.lowerThird.text, ctx, missing) } : null;
    const overlays = (seg.overlays ?? []).map((o) => JSON.parse(fillText(JSON.stringify(o), ctx, missing)));
    out.push({ id: seg.id, name: seg.name, text, lowerThird, overlays, fit: seg.fit ?? 'normal', splitAt: seg.splitAt, splitSeconds: seg.splitSeconds, source: seg.source ?? 'take' });
  }
  const evidence = {
    gvg: `${cap(word(d.report.gemini.wins))} win${d.report.gemini.wins === 1 ? '' : 's'}, ${word(d.report.gemini.losses)} loss${d.report.gemini.losses === 1 ? '' : 'es'} over ${word(d.report.gemini.cases)} budgets`,
    gvgs: 'Single live runs on the Deccan area. Gemini’s output differs between runs; no pass mark.',
    evals: `${d.report.evalsPass} of ${d.report.evalsTotal} evals pass`,
    heat: `Spearman ρ ${d.report.heat.rho}, ${d.report.heat.blocks} held-out blocks, p = ${Number(d.report.heat.p).toFixed(2)}`,
    heats: 'Weak, and not significant. Surface temperature is not the air people feel. The indices are 0–100 screening scores, not temperatures.',
    urls: ['Ankita Sharma', 'github.com/AnkitaShr-Code/EcoZone-AI', 'ecozone-451227459430.asia-south1.run.app'],
  };
  const words = out.reduce((n, s) => n + s.text.split(/\s+/).filter(Boolean).length, 0);
  const result = { take: takeDir, derived: d, evidence, words, missing: [...new Set(missing)], segments: out };
  fs.writeFileSync(path.join(takeDir, 'filled.json'), JSON.stringify(result, null, 2));
  fs.writeFileSync(path.join(ROOT, 'narration-segments.json'), JSON.stringify(out.map((s) => ({ id: s.id, filename: `audio/${s.id}.mp3`, text: s.text })), null, 2));
  fs.writeFileSync(path.join(ROOT, 'narration.md'), `# Narration (filled from ${path.relative(ROOT, takeDir)})\n\n${words} words.\n\n` + out.map((s) => `**${s.id} ${s.name}**\n\n${s.text}\n`).join('\n'));
  return result;
}

if (process.argv[1] === new URL(import.meta.url).pathname) {
  const r = fill(path.resolve(process.argv[2]));
  console.log(`${r.words} words; missing: ${r.missing.join(', ') || 'none'}`);
  for (const s of r.segments) console.log(`${s.id}: ${s.text}`);
}
