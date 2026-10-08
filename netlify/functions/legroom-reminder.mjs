/**
 * Optional Legroom trial emails: one setup email when someone asks for it, and one reminder about five days later.
 * Nothing else, and never a list: each record is deleted when its reminder is sent. The mechanics (endpoint,
 * unsubscribe, rate limits, buyer check, retention) are in netlify/lib/trial-reminder.mjs; this file holds the
 * app's settings and the wording of the two emails, using only what the Legroom page says.
 *
 * POST /.netlify/functions/legroom-reminder             { email, website? }  (the form on /legroom/)
 * GET or POST /.netlify/functions/legroom-reminder?u=<token>                 one-click unsubscribe
 *
 * Blobs: "lg-trial-reminders" (key: email), "lg-trial-reminder-tokens" (key: token). The daily sender is
 * legroom-reminder-send.mjs. Env: RESEND_API_KEY, STRIPE_SECRET_KEY.
 *
 * There is no /legroom/start/ guide, so the setup email links the product page.
 */

import { createTrialReminder, REMIND_AFTER_DAYS } from "../lib/trial-reminder.mjs";

export { REMIND_AFTER_DAYS };

const PAGE = "/legroom/";
const BUY = "/legroom/#buy";
const RECOVER = "/recover/";

const { handler, sendDueReminders, setupEmail, reminderEmail } = createTrialReminder({
  app: "Legroom",
  slug: "legroom",
  fnName: "legroom-reminder",
  store: "lg-trial-reminders",
  tokenStore: "lg-trial-reminder-tokens",
  products: ["legroom", "app-suite"],

  setup: (link) => ({
    subject: "Legroom: getting started",
    text:
      `Thanks for trying Legroom. The trial is the complete app for seven days from the first time you open it, with no account.\n\n` +
      `Three things worth doing in the first few minutes:\n` +
      `1. Look at the free-space figure in the menu bar, then set the low-space line you want to be warned at.\n` +
      `2. Make one cleaning rule for a folder or cache you know is safe, and read its preview. Nothing is removed until you have seen the preview and approved it.\n` +
      `3. Come back to What Grew after a day. Legroom measures once a day, so it has something to compare then.\n\n` +
      `Full Disk Access is optional. Without it, Legroom skips the folders macOS protects, such as Desktop, Documents and Downloads, and tells you which ones it could not read.\n\n` +
      `Each part is described on the Legroom page:\n${link(PAGE)}\n\n` +
      `After the seven days, the menu-bar readout and the low-space alerts keep working and stay free. Cleaning rules, What Grew, Suggestions, Space Map and Find Files stop until you enter a license key. If you buy, the key comes in your receipt email and goes into the same copy, so there is no second download. I will send one more short note around day ${REMIND_AFTER_DAYS}, and then nothing.\n\n` +
      `Questions: reply to this email and I will answer.\n\nBenjamin Ampel`,
    html:
      `<p>Thanks for trying Legroom. The trial is the complete app for seven days from the first time you open it, with no account.</p>` +
      `<p>Three things worth doing in the first few minutes:</p>` +
      `<ol><li>Look at the free-space figure in the menu bar, then set the low-space line you want to be warned at.</li>` +
      `<li>Make one cleaning rule for a folder or cache you know is safe, and read its preview. Nothing is removed until you have seen the preview and approved it.</li>` +
      `<li>Come back to What Grew after a day. Legroom measures once a day, so it has something to compare then.</li></ol>` +
      `<p>Full Disk Access is optional. Without it, Legroom skips the folders macOS protects, such as Desktop, Documents and Downloads, and tells you which ones it could not read.</p>` +
      `<p>Each part is described on <a href="${link(PAGE)}">the Legroom page</a>.</p>` +
      `<p>After the seven days, the menu-bar readout and the low-space alerts keep working and stay free. Cleaning rules, What Grew, Suggestions, Space Map and Find Files stop until you enter a license key. If you buy, the key comes in your receipt email and goes into the same copy, so there is no second download. I will send one more short note around day ${REMIND_AFTER_DAYS}, and then nothing.</p>` +
      `<p>Questions: reply to this email and I will answer.</p><p>Benjamin Ampel</p>`,
  }),

  reminder: (link) => ({
    subject: "Your Legroom trial",
    text:
      `The Legroom trial runs seven days from the first time you open the app, so if you have been trying it this week it ends soon. Nothing is charged when it ends.\n\n` +
      `The menu-bar readout and the low-space alerts keep working and stay free. Cleaning rules, What Grew, Suggestions, Space Map and Find Files stop until you enter a license key.\n\n` +
      `If the cleaning has been useful, keeping it is a single $9.99 payment, with a 14-day refund:\n${link(BUY)}\n\n` +
      `Your license key arrives in the receipt email and is shown on the success page. Choose Enter license key… from the menu-bar dropdown, or Settings, General, and paste it into the copy you already have. It works offline and needs no second download. If you lose the key, the Find a purchase page sends it again:\n${link(RECOVER)}\n\n` +
      `If the free readout is all you need, there is nothing to do. If Legroom was not useful, I would like to know why. Reply to this email with one line.\n\nBenjamin Ampel`,
    html:
      `<p>The Legroom trial runs seven days from the first time you open the app, so if you have been trying it this week it ends soon. Nothing is charged when it ends.</p>` +
      `<p>The menu-bar readout and the low-space alerts keep working and stay free. Cleaning rules, What Grew, Suggestions, Space Map and Find Files stop until you enter a license key.</p>` +
      `<p>If the cleaning has been useful, <a href="${link(BUY)}">keeping it is a single $9.99 payment</a>, with a 14-day refund.</p>` +
      `<p>Your license key arrives in the receipt email and is shown on the success page. Choose Enter license key… from the menu-bar dropdown, or Settings, General, and paste it into the copy you already have. It works offline and needs no second download. If you lose the key, <a href="${link(RECOVER)}">the Find a purchase page</a> sends it again.</p>` +
      `<p>If the free readout is all you need, there is nothing to do. If Legroom was not useful, I would like to know why. Reply to this email with one line.</p><p>Benjamin Ampel</p>`,
  }),
});

export { sendDueReminders, setupEmail, reminderEmail };
export default handler;
