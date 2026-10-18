#!/usr/bin/env node
// frames/ + frames.json (screencast, variable rate) -> raw.mp4 at a constant 30 fps.
// Frame i is shown from its own timestamp until the next one; time 0 is the recording start.
import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';

const take = path.resolve(process.argv[2]);
const { t0, tEnd, frames: all } = JSON.parse(fs.readFileSync(path.join(take, 'frames.json'), 'utf8'));
// Screenshots taken during the recording (stills, map-settle checks) briefly change the screencast's
// metrics and emit frames of another size or crop: drop every frame that is not the main viewport size.
const sizes = {};
for (const f of all) sizes[`${f.w}x${f.h}`] = (sizes[`${f.w}x${f.h}`] ?? 0) + 1;
const main = Object.entries(sizes).sort((a, b) => b[1] - a[1])[0][0];
const frames = all.filter((f) => `${f.w}x${f.h}` === main);
if (frames.length < all.length) console.log(`dropped ${all.length - frames.length} off-size frames (kept ${main})`);
const FPS = 30;
const lines = ['ffconcat version 1.0'];
// Exact constant frame rate: output frame k (time k/30 from recording start) shows the latest
// captured frame at or before that time.
const total = Math.round((tEnd - t0) * FPS);
let j = 0;
for (let k = 0; k < total; k++) {
  const t = t0 + k / FPS;
  while (j + 1 < frames.length && frames[j + 1].t <= t) j++;
  lines.push(`file 'frames/${frames[j].file}'`, `duration ${(1 / FPS).toFixed(6)}`);
}
fs.writeFileSync(path.join(take, 'frames.ffconcat'), lines.join('\n'));
const out = path.join(take, 'raw.mp4');
execFileSync('ffmpeg', ['-y', '-hide_banner', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', path.join(take, 'frames.ffconcat'),
  '-vf', 'scale=1920:1080:flags=lanczos,format=yuv420p', '-r', '30', '-fps_mode', 'cfr', '-c:v', 'libx264', '-preset', 'medium', '-crf', '14', '-movflags', '+faststart', out], { stdio: 'inherit' });
const dur = execFileSync('ffprobe', ['-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', out]).toString().trim();
console.log(`${out} ${dur}s (${frames.length} frames, ${(tEnd - t0).toFixed(1)}s wall)`);
