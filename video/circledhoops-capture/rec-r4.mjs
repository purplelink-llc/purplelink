// Round 4 captures: the pick sheet with a saved Monday pick, a tap on Wednesday, and the app's own ring drawing on,
// sampled frame by frame (the ring's CSS animation is paused and stepped, so every 1/30 s gets a frame); then
// a new league's Teams list as "Add a bot" fills three open spots.
//   node rec-r4.mjs <outdir>
import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { open, B } from './caplib.mjs';

const out = process.argv[2];
fs.mkdirSync(out, { recursive: true });
const { browser, page } = await open();

/** Build a 30 fps clip from [png, seconds] holds and single frames. */
function clip(parts, mp4) {
  const lines = [];
  for (const [file, sec] of parts) lines.push(`file '${file}'`, `duration ${sec.toFixed(4)}`);
  lines.push(`file '${parts[parts.length - 1][0]}'`);
  const list = path.join(out, `${path.basename(mp4, '.mp4')}.txt`);
  fs.writeFileSync(list, lines.join('\n'));
  execFileSync('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', list,
    '-vf', 'fps=30,scale=1170:2532:flags=lanczos,format=yuv420p', '-c:v', 'libx264', '-crf', '14', '-preset', 'slow', mp4]);
}

// ---- the pick sheet ----
await page.goto(`${B}/leagues/lg-demo/lineup`, { waitUntil: 'load' });
await page.waitForTimeout(3000);
await page.getByText('Next week', { exact: true }).first().click();
await page.waitForTimeout(1500);
const row = () => page.getByRole('button', { name: /Tariq Monroe/ }).first();
const games = () => page.locator('[role=dialog] button').filter({ hasText: /PM/ });
// Save Monday as his pick, so the sheet reopens on it.
await row().click();
await page.waitForTimeout(1400);
const mon = await games().nth(0).boundingBox();
await page.mouse.click(mon.x + mon.width / 2, mon.y + mon.height / 2);
await page.waitForTimeout(800);
await page.getByRole('button', { name: 'Save', exact: true }).click();
await page.waitForTimeout(1800);
await row().click();
await page.waitForTimeout(2200);
const monShot = path.join(out, 'r4-sheet-mon.png');
await page.screenshot({ path: monShot });
const wed = await games().nth(1).boundingBox();
fs.writeFileSync(path.join(out, 'r4-boxes.json'), JSON.stringify({ mon, wed, viewport: page.viewportSize() }, null, 1));

// Hold the ring animation at its start, tap Wednesday, then step it.
await page.addStyleTag({ content: '[class*="ring"] path{animation-play-state:paused!important}' });
await page.mouse.click(wed.x + wed.width / 2, wed.y + wed.height / 2);
await page.waitForTimeout(250);
const ringFrames = [];
const DUR = 420, STEP = 1000 / 30;
for (let i = 0, t = 0; t <= DUR + STEP; i++, t += STEP) {
  await page.evaluate((ms) => {
    for (const a of document.getAnimations()) {
      const el = a.effect && a.effect.target;
      if (el && el.closest && el.closest('[class*="ring"]')) { a.pause(); a.currentTime = Math.min(ms, 420); }
    }
  }, t);
  const f = path.join(out, `r4-ring-${String(i).padStart(2, '0')}.png`);
  await page.screenshot({ path: f });
  ringFrames.push(f);
}
const wedShot = ringFrames[ringFrames.length - 1];
fs.copyFileSync(wedShot, path.join(out, 'r4-sheet-wed.png'));
clip([[monShot, 4.0], ...ringFrames.map((f) => [f, 1 / 30]), [wedShot, 4.0]], path.join(out, 'clip-ring.mp4'));
fs.writeFileSync(path.join(out, 'clip-ring.json'), JSON.stringify({ tapAt: 4.0, ringFrames: ringFrames.length }, null, 1));
await page.keyboard.press('Escape');

// ---- a new league: Teams 1 of 8, then "Add a bot" three times ----
await page.goto(`${B}/leagues/new`, { waitUntil: 'load' });
await page.waitForTimeout(3500);
const ins = page.locator('input');
await ins.nth(0).fill('Rim Runners');
await ins.nth(1).fill('Thursday Night Hoops');
await page.getByRole('button', { name: 'Create league' }).click();
await page.waitForTimeout(3500);
const teamsShots = [path.join(out, 'r4-teams-0.png')];
await page.screenshot({ path: teamsShots[0] });
const add = page.getByRole('button', { name: 'Add a bot', exact: true });
const addBox = (await add.count()) ? await add.first().boundingBox() : null;
const adds = [];
for (let i = 1; i <= 3 && (await add.count()); i++) {
  const box = await add.first().boundingBox();
  adds.push(box);
  await add.first().click();
  await page.waitForTimeout(1300);
  const f = path.join(out, `r4-teams-${i}.png`);
  await page.screenshot({ path: f });
  teamsShots.push(f);
}
// The same list once the toast has gone, for crops that would cut it in half.
await page.waitForTimeout(6000);
await page.screenshot({ path: path.join(out, 'r4-teams-final.png') });
fs.writeFileSync(path.join(out, 'r4-teams.json'), JSON.stringify({ addBox, adds, viewport: page.viewportSize() }, null, 1));
clip(teamsShots.map((f, i) => [f, i === 0 ? 1.6 : i === teamsShots.length - 1 ? 3.5 : 0.9]), path.join(out, 'clip-bots.mp4'));
console.log('done', ringFrames.length, 'ring frames; add a bot', !!addBox);
await browser.close();
