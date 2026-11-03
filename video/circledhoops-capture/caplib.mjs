import { chromium } from 'playwright';
export const B = 'http://localhost:3217';
export async function open({ w=390, h=844, video=null } = {}) {
  const browser = await chromium.launch();
  const opts = { viewport:{width:w,height:h}, deviceScaleFactor:3, colorScheme:'dark', isMobile:true, hasTouch:true };
  if (video) opts.recordVideo = { dir: video, size: { width: w*2, height: h*2 } };
  const ctx = await browser.newContext(opts);
  await ctx.addInitScript(() => {
    const css = 'nextjs-portal{display:none!important} [class*="DraftBeacon"]{display:none!important}';
    const add = () => { const s=document.createElement('style'); s.textContent=css; document.documentElement.appendChild(s); };
    if (document.documentElement) add(); else document.addEventListener('DOMContentLoaded', add);
  });
  const page = await ctx.newPage();
  await page.goto(`${B}/leagues/lg-demo/lineup`, { waitUntil:'load', timeout:90000 });
  await page.waitForTimeout(4000);
  const fill = page.getByText('Fill demo account');
  if (await fill.count()) {
    await fill.first().click();
    await page.getByRole('button', { name: 'Sign in', exact: true }).click();
    await page.waitForTimeout(3000);
    await page.waitForTimeout(2000);
  }
  return { browser, ctx, page };
}

// CDP screencast: JPEG frames with timestamps, assembled to CFR 30 fps by toMp4().
import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
export async function record(page, dir) {
  fs.rmSync(dir, { recursive: true, force: true }); fs.mkdirSync(dir, { recursive: true });
  const cdp = await page.context().newCDPSession(page);
  const frames = []; let stopped = false;
  cdp.on('Page.screencastFrame', async (f) => {
    if (stopped) return;
    const m = f.metadata;
    if (Math.abs((m.pageScaleFactor ?? 1) - 1) > 0.01 || Math.round(m.deviceWidth) !== Math.round(page.viewportSize().width)) {
      try { await cdp.send('Page.screencastFrameAck', { sessionId: f.sessionId }); } catch {}
      return;
    }
    const n = frames.length; const file = path.join(dir, `f${String(n).padStart(5,'0')}.jpg`);
    fs.writeFileSync(file, Buffer.from(f.data, 'base64'));
    frames.push({ file, t: f.metadata.timestamp });
    try { await cdp.send('Page.screencastFrameAck', { sessionId: f.sessionId }); } catch {}
  });
  await cdp.send('Page.startScreencast', { format: 'jpeg', quality: 94, maxWidth: 1170, maxHeight: 2532, everyNthFrame: 1 });
  const t0 = Date.now() / 1000;
  return {
    marks: [], mark(name) { this.marks.push({ name, t: Date.now() / 1000 - t0 }); },
    async stop(mp4) {
      await page.waitForTimeout(300);
      await cdp.send('Page.stopScreencast'); stopped = true;
      const end = Date.now() / 1000;
      const lines = [];
      for (let i = 0; i < frames.length; i++) {
        const d = (i + 1 < frames.length ? frames[i + 1].t : end) - frames[i].t;
        lines.push(`file '${frames[i].file}'`, `duration ${Math.max(0.001, d).toFixed(4)}`);
      }
      lines.push(`file '${frames[frames.length - 1].file}'`);
      fs.writeFileSync(path.join(dir, 'list.txt'), lines.join('\n'));
      execFileSync('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', path.join(dir, 'list.txt'),
        '-vf', 'fps=30,scale=1170:2532:flags=lanczos,format=yuv420p', '-c:v', 'libx264', '-crf', '14', '-preset', 'slow', mp4]);
      const startOffset = frames[0].t - t0;
      fs.writeFileSync(mp4.replace(/\.mp4$/, '.json'), JSON.stringify({ frames: frames.length, startOffset, marks: this.marks }, null, 1));
      fs.rmSync(dir, { recursive: true, force: true });
      return frames.length;
    },
  };
}
// Draw a loose hand-made ellipse around a box with the pointer, the way a thumb would.
export async function drawCircle(page, box, { steps = 60, ms = 1100 } = {}) {
  const cx = box.x + box.width / 2, cy = box.y + box.height / 2;
  const rx = box.width * 0.78, ry = box.height * 0.47;
  const pt = (a, k = 1) => [cx + rx * k * Math.cos(a), cy + ry * k * Math.sin(a)];
  const a0 = -Math.PI * 0.62;
  let [x, y] = pt(a0);
  await page.mouse.move(x, y); await page.mouse.down();
  for (let i = 1; i <= steps; i++) {
    const a = a0 + (i / steps) * Math.PI * 2.12;
    const k = 1 + 0.05 * Math.sin(i * 0.7);
    [x, y] = pt(a, k);
    await page.mouse.move(x, y);
    await page.waitForTimeout(ms / steps);
  }
  await page.mouse.up();
}
