// High-quality screen capture through the Chrome DevTools screencast.
// Playwright's recordVideo needs its own downloaded ffmpeg build and encodes low-bitrate VP8,
// so we capture JPEG frames with their timestamps and assemble a constant-frame-rate video later.
import fs from 'node:fs';
import path from 'node:path';

export async function startRecorder(page, outDir, { width = 1920, height = 1080, quality = 92 } = {}) {
  const framesDir = path.join(outDir, 'frames');
  fs.rmSync(framesDir, { recursive: true, force: true });
  fs.mkdirSync(framesDir, { recursive: true });
  const cdp = await page.context().newCDPSession(page);
  const frames = [];
  let n = 0;
  let stopped = false;
  cdp.on('Page.screencastFrame', async ({ data, metadata, sessionId }) => {
    if (!stopped) {
      const file = `${String(n++).padStart(6, '0')}.jpg`;
      fs.writeFileSync(path.join(framesDir, file), Buffer.from(data, 'base64'));
      frames.push({ file, t: metadata.timestamp ?? Date.now() / 1000, w: metadata.deviceWidth, h: metadata.deviceHeight });
    }
    try { await cdp.send('Page.screencastFrameAck', { sessionId }); } catch { /* closed */ }
  });
  const t0 = Date.now() / 1000;
  await cdp.send('Page.startScreencast', { format: 'jpeg', quality, maxWidth: width, maxHeight: height, everyNthFrame: 1 });
  return {
    t0,
    /** ms since recording start, on the same clock as the frames. */
    now: () => Date.now() - t0 * 1000,
    async stop() {
      try { await cdp.send('Page.stopScreencast'); } catch { /* closed */ }
      stopped = true;
      const tEnd = Date.now() / 1000;
      fs.writeFileSync(path.join(outDir, 'frames.json'), JSON.stringify({ t0, tEnd, frames }, null, 0));
      return { t0, tEnd, count: frames.length };
    },
  };
}
