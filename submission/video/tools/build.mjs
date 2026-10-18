#!/usr/bin/env node
// Audio-driven edit. Each narration file sets its segment's length; the screen recording is
// trimmed, sped up or held to fit it; overlays are rendered from HTML and composited; the
// segments are joined and the narration (plus an optional soft synthesized pad) is mixed in.
//
//   node tools/build.mjs --take takes/take2 --voice-dir audio/ --out out/final.mp4
//   node tools/build.mjs --take takes/take2 --tts say --out out/rehearsal.mp4
import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { fill } from './fill.mjs';
import { renderGraphic, closeGfx, FPS } from './gfx.mjs';
import { shadeGain } from './shadediff.mjs';

const HERE = path.dirname(new URL(import.meta.url).pathname);
const ROOT = path.resolve(HERE, '..');
const args = process.argv.slice(2);
const arg = (k, d) => { const i = args.indexOf(k); return i >= 0 ? args[i + 1] : d; };
const flag = (k) => args.includes(k);
const TAKE = path.resolve(ROOT, arg('--take', fs.readFileSync(path.join(ROOT, 'takes/CURRENT'), 'utf8').trim()));
const OUT = path.resolve(ROOT, arg('--out', 'out/final.mp4'));
const TTS = arg('--tts', null);
const VOICE = arg('--voice-dir', null);
const MUSIC = !flag('--no-music');
const BUILD = path.join(ROOT, 'build', path.basename(OUT, '.mp4'));
const GFXCACHE = path.join(ROOT, 'build', 'gfx');
const script = JSON.parse(fs.readFileSync(path.join(ROOT, 'script.json'), 'utf8'));
const LEAD = script.leadSeconds, TAIL = script.tailSeconds;
const DSF_BOX_SCALE = 1; // boxes in values.json are already in video pixels

fs.mkdirSync(BUILD, { recursive: true });
fs.mkdirSync(path.dirname(OUT), { recursive: true });
const ff = (a, opts = {}) => execFileSync('ffmpeg', ['-y', '-hide_banner', '-loglevel', 'error', ...a], { stdio: ['ignore', 'inherit', 'inherit'], ...opts });
const probeDur = (f) => Number(execFileSync('ffprobe', ['-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', f]).toString().trim());
const log = (...m) => console.log('[build]', ...m);
const r3 = (x) => Math.round(x * 1000) / 1000;

// ---------- 1. narration text from the take ----------
const filled = fill(TAKE);
if (filled.missing.length) { console.error(`Unfilled placeholders: ${filled.missing.join(', ')}`); process.exit(1); }
const values = JSON.parse(fs.readFileSync(path.join(TAKE, 'values.json'), 'utf8'));
const markers = Object.fromEntries(JSON.parse(fs.readFileSync(path.join(TAKE, 'markers.json'), 'utf8')).segments.map((m) => [m.id, m]));
const raw = path.join(TAKE, 'raw.mp4');
if (!fs.existsSync(raw)) execFileSync('node', [path.join(HERE, 'assemble.mjs'), TAKE], { stdio: 'inherit' });

// ---------- 2. audio per segment ----------
const audioDir = path.join(BUILD, 'audio');
fs.mkdirSync(audioDir, { recursive: true });
for (const s of filled.segments) {
  const wav = path.join(audioDir, `${s.id}.wav`);
  if (TTS === 'say') {
    const aiff = path.join(audioDir, `${s.id}.aiff`);
    execFileSync('say', ['-v', arg('--voice', 'Tara'), '-r', arg('--rate', '178'), '-o', aiff, s.text]);
    ff(['-i', aiff, '-ar', '48000', '-ac', '1', wav]);
  } else {
    const dir = path.resolve(ROOT, VOICE ?? 'audio');
    const src = ['mp3', 'wav', 'm4a', 'aiff'].map((e) => path.join(dir, `${s.id}.${e}`)).find((f) => fs.existsSync(f));
    if (!src) { console.error(`Missing narration audio for ${s.id} in ${dir}`); process.exit(1); }
    // Trim leading and trailing silence so pacing is ours, not the TTS engine's.
    ff(['-i', src, '-af', 'silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.05,areverse,silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.08,areverse', '-ar', '48000', '-ac', '1', wav]);
  }
  s.audio = wav;
  s.audioDur = probeDur(wav);
  s.dur = r3(Math.ceil((LEAD + s.audioDur + TAIL) * FPS) / FPS);
}

// ---------- 3. fit the screen recording to each segment ----------
/** Pieces of source [a, b) at speed `sp`, then a freeze. Returns pieces and a source->output time map. */
function plan(s) {
  const m = markers[s.id];
  const D = s.dur;
  const st = m.start / 1000, ae = m.actionsEnd / 1000, en = m.end / 1000;
  const A = ae - st;
  const pieces = [];
  let info = {};
  if (s.fit === 'timelapse') {
    const tailOut = Math.min(1.4, Math.max(0.6, D * 0.12));
    const sp = A / (D - tailOut);
    pieces.push({ a: st, b: ae, sp });
    pieces.push({ a: ae, b: Math.min(en, ae + tailOut), sp: 1 });
    info = { timelapse: { out: (ae - st) / sp, speed: sp } };
  } else if (s.fit === 'split') {
    const se = (m.searchEnd ?? m.actionsEnd) / 1000;
    const out1 = s.splitSeconds;
    pieces.push({ a: st, b: se, sp: (se - st) / out1 });
    const rest = D - out1;
    const A2 = ae - se;
    if (A2 <= rest) pieces.push({ a: se, b: Math.min(en, se + rest), sp: 1 });
    else pieces.push({ a: se, b: ae, sp: A2 / rest });
    info = { split: { out: out1, speed: (se - st) / out1 } };
  } else if (A <= D) {
    pieces.push({ a: st, b: Math.min(en, st + D), sp: 1 });
  } else {
    const sp = A / D;
    if (sp > 1.6) log(`WARN ${s.id}: actions ${A.toFixed(1)}s squeezed into ${D.toFixed(1)}s (x${sp.toFixed(2)})`);
    pieces.push({ a: st, b: ae, sp });
  }
  let t = 0;
  for (const p of pieces) { p.outStart = t; p.outLen = (p.b - p.a) / p.sp; t += p.outLen; }
  const freeze = Math.max(0, D - t);
  const map = (srcSec) => {
    for (const p of pieces) if (srcSec >= p.a && srcSec <= p.b) return p.outStart + (srcSec - p.a) / p.sp;
    return srcSec < pieces[0].a ? 0 : t;
  };
  return { pieces, freeze, map, info };
}

// ---------- 4. overlays ----------
async function overlaysFor(s, fit) {
  const D = s.dur;
  const list = [];
  if (s.lowerThird) list.push({ graphic: 'lowerthird', params: s.lowerThird, at: 0.35, dur: Math.min(D - 0.5, s.lowerThird.dur ?? 6.5) });
  for (const o of s.overlays) {
    let at = o.at, dur = o.dur;
    if (o.box === '@shadeGain') {
      const g = shadeGain(path.join(TAKE, 'stills/06a-shade-3pm-today.png'), path.join(TAKE, 'stills/06b-shade-3pm-with-plan.png'));
      if (!g) { log(`WARN ${s.id}: no footpath turned from sun to shade between the stills; callout skipped`); continue; }
      values.boxes['@shadeGain'] = { ...g, t: 0 };
      log(`${s.id}: shade gain at ${JSON.stringify(g)}`);
    }
    if (o.box) {
      const b = values.boxes?.[o.box];
      if (!b || b.w == null) { log(`WARN ${s.id}: box ${o.box} missing, callout skipped`); continue; }
      if (at === 'box') at = Math.max(0.2, fit.map(b.t / 1000) - 0.3);
      // The highlighted element moves when the panel scrolls: end the callout before that.
      if (b.tEnd != null && typeof at === 'number') dur = Math.min(typeof dur === 'number' ? dur : 99, fit.map(b.tEnd / 1000) - at);
    }
    if (at === 'split') at = fit.info.split?.out ?? 0;
    if (typeof at === 'string' && at.startsWith('mark:')) {
      // A moment the harness logged (ms from recording start); older takes fall back to just before the actions end.
      const ms = values.marks?.[at.slice(5)] ?? (markers[s.id].actionsEnd - 2600);
      at = fit.map(ms / 1000) + 0.7;
    }
    if (typeof at === 'string') at = Number(at) < 0 ? D + Number(at) : Number(at);
    if (dur === 'segment') dur = D - at;
    if (dur === 'timelapse') dur = Math.max(1, (fit.info.timelapse?.out ?? D) - at);
    if (dur === 'split') dur = Math.max(1, (fit.info.split?.out ?? D) - at);
    dur = Math.min(dur, D - at);
    if (dur <= 0.3) continue;
    const params = { ...o };
    delete params.graphic; delete params.at; delete params.dur;
    if (o.box) params.box = values.boxes[o.box];
    if (o.graphic === 'speed') {
      const sp = fit.info.timelapse?.speed ?? fit.info.split?.speed;
      params.text = o.text.replace('Sped up', `Sped up ${Math.round(sp)}×`);
    }
    if (o.graphic === 'evidence') Object.assign(params, filled.evidence, { cues: evidenceCues(s, D) });
    list.push({ graphic: o.graphic, params, at, dur });
  }
  for (const o of list) o.r = await renderGraphic(o.graphic, o.params, r3(o.dur), GFXCACHE);
  return list;
}

/** Reveal each evidence card as the narration reaches it (by character position in the text). */
function evidenceCues(s, D) {
  const text = s.text;
  const at = (needle) => { const i = text.indexOf(needle); return i < 0 ? null : LEAD + (i / text.length) * s.audioDur; };
  return [at('Gemini proposes') ?? 1.5, at('live Gemini') ?? 5, at('We report') ?? 4, at('Our heat index') ?? 12, Math.max(D - 5.5, (at('EcoZone AI:') ?? D - 5) - 0.3)].map((x) => r3(Math.max(0.6, x - 0.2)));
}

// ---------- 5. render each segment ----------
const segFiles = [];
let prevSeg = null;
for (const s of filled.segments) {
  const out = path.join(BUILD, `${s.id}.mp4`);
  const inputs = [];
  const filters = [];
  let base;
  let fit = { map: () => 0, info: {}, pieces: [], freeze: s.dur };
  if (s.source === 'graphic') {
    const bg = path.join(BUILD, `${s.id}-bg.png`);
    ff(['-sseof', '-0.1', '-i', prevSeg, '-frames:v', '1', '-update', '1', bg]);
    inputs.push('-loop', '1', '-framerate', String(FPS), '-t', String(s.dur), '-i', bg);
    filters.push(`[0:v]boxblur=18:2,eq=brightness=-0.04,format=yuv420p,setsar=1[base]`);
    base = 'base';
  } else {
    fit = plan(s);
    fit.pieces.forEach((p, i) => {
      inputs.push('-ss', String(r3(p.a)), '-t', String(r3(p.b - p.a + 0.2)), '-i', raw);
      filters.push(`[${i}:v]trim=duration=${r3(p.b - p.a)},setpts=(PTS-STARTPTS)/${r3(p.sp)},fps=${FPS}[p${i}]`);
    });
    const n = fit.pieces.length;
    filters.push(`${fit.pieces.map((_, i) => `[p${i}]`).join('')}concat=n=${n}:v=1:a=0,tpad=stop_mode=clone:stop_duration=${r3(fit.freeze + 0.5)},trim=duration=${s.dur},setsar=1[base]`);
    base = 'base';
    s.fitInfo = { pieces: fit.pieces.map((p) => ({ a: r3(p.a), b: r3(p.b), speed: r3(p.sp), outStart: r3(p.outStart), outLen: r3(p.outLen) })), freeze: r3(fit.freeze), ...fit.info };
  }
  const ovs = await overlaysFor(s, fit);
  let cur = base;
  const k0 = inputs.filter((x) => x === '-i').length;
  ovs.forEach((o, j) => {
    inputs.push('-framerate', String(FPS), '-i', path.join(o.r.dir, '%05d.png'));
    filters.push(`[${k0 + j}:v]format=rgba,setpts=PTS-STARTPTS+${r3(o.at)}/TB[g${j}]`);
    filters.push(`[${cur}][g${j}]overlay=eof_action=pass:format=auto[v${j}]`);
    cur = `v${j}`;
  });
  filters.push(`[${cur}]format=yuv420p[out]`);
  ff([...inputs, '-filter_complex', filters.join(';'), '-map', '[out]', '-t', String(s.dur), '-r', String(FPS), '-c:v', 'libx264', '-preset', 'medium', '-crf', '15', '-pix_fmt', 'yuv420p', out]);
  s.overlaysUsed = ovs.map((o) => ({ graphic: o.graphic, at: r3(o.at), dur: r3(o.dur) }));
  log(`${s.id} ${s.dur.toFixed(2)}s (audio ${s.audioDur.toFixed(2)}s) ${s.fitInfo ? JSON.stringify(s.fitInfo.pieces.map((p) => `x${p.speed}`)) + ` freeze ${s.fitInfo.freeze}` : 'graphic'}`);
  segFiles.push(out);
  prevSeg = out;
}
await closeGfx();

// ---------- 6. join video, build the narration track, mix, encode ----------
const total = r3(filled.segments.reduce((t, s) => t + s.dur, 0));
const list = path.join(BUILD, 'segments.txt');
fs.writeFileSync(list, segFiles.map((f) => `file '${f}'`).join('\n'));
const video = path.join(BUILD, 'video.mp4');
ff(['-f', 'concat', '-safe', '0', '-i', list, '-c', 'copy', video]);

const narr = path.join(BUILD, 'narration.wav');
{
  const ins = [];
  const fl = [];
  let t = 0;
  filled.segments.forEach((s, i) => {
    ins.push('-i', s.audio);
    const delay = Math.round((t + LEAD) * 1000);
    fl.push(`[${i}:a]adelay=${delay}|${delay}[a${i}]`);
    s.start = r3(t);
    t += s.dur;
  });
  fl.push(`${filled.segments.map((_, i) => `[a${i}]`).join('')}amix=inputs=${filled.segments.length}:normalize=0,apad=whole_dur=${total},atrim=0:${total}[n]`);
  ff([...ins, '-filter_complex', fl.join(';'), '-map', '[n]', '-ar', '48000', '-ac', '1', narr]);
}

let mixInputs = ['-i', video, '-i', narr];
let afilter = `[1:a]loudnorm=I=-16:TP=-1.5:LRA=11,aformat=channel_layouts=stereo[nar]`;
let amap = '[nar]';
if (MUSIC) {
  // A very soft synthesized pad: an A major add9 chord of sines with slow swells, low-passed.
  const pad = path.join(BUILD, 'pad.wav');
  const expr = ['110', '164.81', '220', '277.18', '329.63', '493.88'].map((f, i) => `${[0.5, 0.35, 0.3, 0.18, 0.16, 0.08][i]}*sin(2*PI*${f}*t)*(0.6+0.4*sin(2*PI*${(0.05 + i * 0.013).toFixed(3)}*t+${i}))`).join('+');
  ff(['-f', 'lavfi', '-i', `aevalsrc=${expr}:s=48000:d=${total}`, '-af', `lowpass=f=900,volume=0.05,afade=t=in:d=3,afade=t=out:st=${Math.max(0, total - 4)}:d=4,aformat=channel_layouts=stereo`, pad]);
  mixInputs.push('-i', pad);
  afilter += `;[2:a]volume=0.55[pad];[nar][pad]amix=inputs=2:normalize=0:duration=first[mix]`;
  amap = '[mix]';
}
ff([...mixInputs, '-filter_complex', `${afilter};[0:v]fade=t=in:d=0.5,fade=t=out:st=${r3(total - 0.8)}:d=0.8[v]`, '-map', '[v]', '-map', amap,
  '-c:v', 'libx264', '-preset', 'slow', '-crf', '17', '-pix_fmt', 'yuv420p', '-r', String(FPS), '-profile:v', 'high',
  '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', '-movflags', '+faststart', '-t', String(total), OUT]);

// ---------- 7. captions ----------
const ts = (x) => { const ms = Math.round(x * 1000); const h = Math.floor(ms / 3600000), m = Math.floor(ms / 60000) % 60, sec = Math.floor(ms / 1000) % 60; return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')},${String(ms % 1000).padStart(3, '0')}`; };
const cues = [];
for (const s of filled.segments) {
  const chunks = s.text.match(/[^.!?:]+[.!?:]+|[^.!?:]+$/g).map((c) => c.trim()).filter(Boolean);
  const totalChars = chunks.reduce((n, c) => n + c.length, 0);
  let t = s.start + LEAD;
  for (const c of chunks) {
    const d = (c.length / totalChars) * s.audioDur;
    cues.push({ a: t, b: t + d, text: c });
    t += d;
  }
}
const srt = cues.map((c, i) => `${i + 1}\n${ts(c.a)} --> ${ts(c.b)}\n${c.text}\n`).join('\n');
fs.writeFileSync(path.join(path.dirname(OUT), path.basename(OUT, '.mp4') === 'final' ? 'captions.srt' : `${path.basename(OUT, '.mp4')}.srt`), srt);

const outDur = probeDur(OUT);
fs.writeFileSync(path.join(BUILD, 'edl.json'), JSON.stringify({ take: TAKE, out: OUT, duration: outDur, segments: filled.segments.map((s) => ({ id: s.id, start: s.start, dur: s.dur, audioDur: r3(s.audioDur), fit: s.fitInfo ?? 'graphic', overlays: s.overlaysUsed, text: s.text })) }, null, 2));
log(`${OUT} ${outDur.toFixed(2)}s ${outDur >= 180 ? 'OVER THE 3:00 CAP' : 'under 3:00'}`);
