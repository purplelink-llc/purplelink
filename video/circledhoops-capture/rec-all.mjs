import { open, B, record } from './caplib.mjs';
const out = process.argv[2];
const which = process.argv.slice(3);
const go = async (page, r) => { await page.goto(`${B}/leagues/lg-demo/${r}`, { waitUntil: 'load' }); await page.waitForTimeout(3500); };
const scroll = async (page, dy, ms) => { const steps = Math.round(ms / 16); for (let i = 0; i < steps; i++) { await page.mouse.wheel(0, dy / steps); await page.waitForTimeout(16); } };
const clips = {
  async matchup(page) {
    await go(page, 'matchup');
    const rec = await record(page, `${out}/_f_matchup`);
    await page.waitForTimeout(9000);
    await scroll(page, 520, 1500); await page.waitForTimeout(3500);
    await rec.stop(`${out}/clip-matchup.mp4`);
  },
  async autoset(page) {
    await go(page, 'lineup');
    await page.getByText('Next week', { exact: true }).first().click(); await page.waitForTimeout(1500);
    const rec = await record(page, `${out}/_f_autoset`);
    await page.waitForTimeout(1000); rec.mark('tap');
    await page.getByRole('button', { name: 'Auto-set lineup' }).click();
    await page.waitForTimeout(3500);
    await rec.stop(`${out}/clip-autoset.mp4`);
    await page.screenshot({ path: `${out}/still-autoset.png` });
  },
  async chat(page) {
    await go(page, 'chat');
    await page.mouse.move(195, 400);
    await scroll(page, -4000, 200); await page.waitForTimeout(800);
    const rec = await record(page, `${out}/_f_chat`);
    await page.waitForTimeout(800); await scroll(page, 4000, 6000); await page.waitForTimeout(1200);
    await rec.stop(`${out}/clip-chat.mp4`);
  },
  async thisweek(page) {
    await go(page, 'lineup');
    await page.screenshot({ path: `${out}/still-lineup-locked.png` });
    await page.screenshot({ path: `${out}/still-lineup-locked-full.png`, fullPage: true });
  },
  async stills(page) {
    for (const r of ['standings', 'history', 'league', 'cup', 'players', 'draft', 'trades']) {
      await go(page, r);
      await page.screenshot({ path: `${out}/still-${r}.png` });
      await page.screenshot({ path: `${out}/still-${r}-full.png`, fullPage: true });
    }
  },
};
for (const w of which) {
  const { browser, page } = await open();
  try { await clips[w](page); console.log('ok', w); } catch (e) { console.log('fail', w, e.message.slice(0, 200)); }
  await browser.close();
}
