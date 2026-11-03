/**
 * Optional Née trial emails: one setup email when someone asks for it, and one reminder about five days later.
 * Nothing else, and never a list: each record is deleted when its reminder is sent. The mechanics (endpoint,
 * unsubscribe, rate limits, buyer check, retention) are in netlify/lib/trial-reminder.mjs; this file holds the
 * app's settings and the wording of the two emails, using only what the Née page says.
 *
 * POST /.netlify/functions/nee-reminder             { email, website? }  (the form on /nee/)
 * GET or POST /.netlify/functions/nee-reminder?u=<token>                 one-click unsubscribe
 *
 * Blobs: "nee-trial-reminders" (key: email), "nee-trial-reminder-tokens" (key: token). The daily sender is
 * nee-reminder-send.mjs. Env: RESEND_API_KEY, STRIPE_SECRET_KEY.
 *
 * There is no /nee/start/ guide, so the setup email links the product page.
 */

import { createTrialReminder, REMIND_AFTER_DAYS } from "../lib/trial-reminder.mjs";

export { REMIND_AFTER_DAYS };

const PAGE = "/nee/";
const BUY = "/nee/#buy";
const RECOVER = "/recover/";

const { handler, sendDueReminders, setupEmail, reminderEmail } = createTrialReminder({
  app: "Née",
  slug: "nee",
  fnName: "nee-reminder",
  store: "nee-trial-reminders",
  tokenStore: "nee-trial-reminder-tokens",
  // A Mac Suite buyer counts as a buyer, so is never nudged to buy.
  products: ["nee", "app-suite"],

  setup: (link) => ({
    subject: "Née: getting started",
    text:
      `Thanks for trying Née. Everything it does runs on your Mac, and nothing you drop on it is uploaded.\n\n` +
      `Three things worth knowing in the first few minutes:\n` +
      `1. Start dragging a file in Finder, then hold Option. The ring opens at the pointer; drop the file on a slice and the result is saved next to the original. The original is not changed.\n` +
      `2. You can also drop files on the menu-bar item or the Dock icon, or choose a file in Finder and use Services. Every action is in the ring that opens from those too.\n` +
      `3. History in the menu-bar window lists every result, and Undo moves a job's results to the Trash.\n\n` +
      `Each action is described on the Née page:\n${link(PAGE)}\n\n` +
      `The trial is the complete app for seven days from the first time you open it, with no account. After that you need a license key. If you buy, the key comes in your receipt email and goes into the same copy, so there is no second download. I will send one more short note around day ${REMIND_AFTER_DAYS}, and then nothing.\n\n` +
      `Questions: reply to this email and I will answer.\n\nBenjamin Ampel`,
    html:
      `<p>Thanks for trying Née. Everything it does runs on your Mac, and nothing you drop on it is uploaded.</p>` +
      `<p>Three things worth knowing in the first few minutes:</p>` +
      `<ol><li>Start dragging a file in Finder, then hold Option. The ring opens at the pointer; drop the file on a slice and the result is saved next to the original. The original is not changed.</li>` +
      `<li>You can also drop files on the menu-bar item or the Dock icon, or choose a file in Finder and use Services. Every action is in the ring that opens from those too.</li>` +
      `<li>History in the menu-bar window lists every result, and Undo moves a job's results to the Trash.</li></ol>` +
      `<p>Each action is described on <a href="${link(PAGE)}">the Née page</a>.</p>` +
      `<p>The trial is the complete app for seven days from the first time you open it, with no account. After that you need a license key. If you buy, the key comes in your receipt email and goes into the same copy, so there is no second download. I will send one more short note around day ${REMIND_AFTER_DAYS}, and then nothing.</p>` +
      `<p>Questions: reply to this email and I will answer.</p><p>Benjamin Ampel</p>`,
  }),

  reminder: (link) => ({
    subject: "Your Née trial",
    text:
      `The Née trial runs seven days from the first time you open the app, so if you have been trying it this week it ends soon. When it ends the ring still opens, but running an action asks for a license key; nothing is charged. History and Undo keep working.\n\n` +
      `If you want to keep it, Née is a single $14.99 payment, with every update included and a 14-day refund:\n${link(BUY)}\n\n` +
      `Your license key arrives in the receipt email and is shown on the page after you pay. Choose Enter License Key in Née and paste it into the copy you already have. It works offline and needs no second download. If you lose the key, the Find a purchase page sends it again:\n${link(RECOVER)}\n\n` +
      `If Née was not for you, I would like to know why. Reply to this email with one line.\n\nBenjamin Ampel`,
    html:
      `<p>The Née trial runs seven days from the first time you open the app, so if you have been trying it this week it ends soon. When it ends the ring still opens, but running an action asks for a license key; nothing is charged. History and Undo keep working.</p>` +
      `<p>If you want to keep it, <a href="${link(BUY)}">Née is a single $14.99 payment</a>, with every update included and a 14-day refund.</p>` +
      `<p>Your license key arrives in the receipt email and is shown on the page after you pay. Choose Enter License Key in Née and paste it into the copy you already have. It works offline and needs no second download. If you lose the key, <a href="${link(RECOVER)}">the Find a purchase page</a> sends it again.</p>` +
      `<p>If Née was not for you, I would like to know why. Reply to this email with one line.</p><p>Benjamin Ampel</p>`,
  }),
});

export { sendDueReminders, setupEmail, reminderEmail };
export default handler;
