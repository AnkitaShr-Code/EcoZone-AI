// Find where the plan turns footpath from "in sun" to "in shade" on the map, by comparing the
// take's two stills (today / with plan) pixel by pixel in the app's own footpath colours.
// Returns the densest such window in video pixels, or null.
import { execFileSync } from 'node:child_process';

const W = 960, H = 540; // half resolution
const SUN = [0xe8, 0xa3, 0x3d], SHADE = [0x1f, 0x8a, 0x70], DEPAVE = [0x2a, 0x8c, 0x9e];
const dist = (r, g, b, c) => Math.abs(r - c[0]) + Math.abs(g - c[1]) + Math.abs(b - c[2]);
const near = (r, g, b, c, tol) => Math.abs(r - c[0]) + Math.abs(g - c[1]) + Math.abs(b - c[2]) < tol;


export function shadeGain(todayPng, planPng, { win = 70 } = {}) {
  const a = execFileSync('ffmpeg', ['-v', 'error', '-i', todayPng, '-vf', `scale=${W}:${H}:flags=neighbor`, '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], { maxBuffer: 64 << 20 });
  const b = execFileSync('ffmpeg', ['-v', 'error', '-i', planPng, '-vf', `scale=${W}:${H}:flags=neighbor`, '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], { maxBuffer: 64 << 20 });
  // Integral image of "was sun, now shade" pixels inside the map (right of the panel, clear of the legend and controls).
  const I = new Int32Array((W + 1) * (H + 1));
  let total = 0;
  for (let y = 0; y < H; y++) {
    let row = 0;
    for (let x = 0; x < W; x++) {
      const i = (y * W + x) * 3;
      const inMap = x > 250 && y > 40 && y < 480 && !(x > 850 && y > 300);
      const hit = inMap && near(a[i], a[i + 1], a[i + 2], SUN, 90) && near(b[i], b[i + 1], b[i + 2], SHADE, 45) && dist(b[i], b[i + 1], b[i + 2], SHADE) < dist(b[i], b[i + 1], b[i + 2], DEPAVE) - 15 ? 1 : 0;
      row += hit; total += hit;
      I[(y + 1) * (W + 1) + x + 1] = I[y * (W + 1) + x + 1] + row;
    }
  }
  if (total < 20) return null;
  let best = { n: 0 };
  for (let y = 0; y + win <= H; y += 4) {
    for (let x = 0; x + win <= W; x += 4) {
      const n = I[(y + win) * (W + 1) + x + win] - I[y * (W + 1) + x + win] - I[(y + win) * (W + 1) + x] + I[y * (W + 1) + x];
      if (n > best.n) best = { n, x, y };
    }
  }
  return { x: best.x * 2, y: best.y * 2, w: win * 2, h: win * 2, pixels: best.n, total };
}
