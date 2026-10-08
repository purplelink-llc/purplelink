/**
 * Optional Keyfeel trial emails: one setup email when someone asks for it, and one reminder about five days later.
 * Nothing else, and never a list: each record is deleted when its reminder is sent. The mechanics (endpoint,
 * unsubscribe, rate limits, buyer check, retention) are in netlify/lib/trial-reminder.mjs; this file holds the
 * app's settings and the wording of the two emails, using only what the Keyfeel page says.
 *
 * POST /.netlify/functions/keyfeel-reminder             { email, website? }  (the form on /keyfeel/)
 * GET or POST /.netlify/functions/keyfeel-reminder?u=<token>                 one-click unsubscribe
 *
 * Blobs: "kf-trial-reminders" (key: email), "kf-trial-reminder-tokens" (key: token). The daily sender is
 * keyfeel-reminder-send.mjs. Env: RESEND_API_KEY, STRIPE_SECRET_KEY.
 *
 * There is no /keyfeel/start/ guide, so the setup email links the product page.
 */

import { createTrialReminder, REMIND_AFTER_DAYS } from "../lib/trial-reminder.mjs";

export { REMIND_AFTER_DAYS };

const PAGE = "/keyfeel/";
const BUY = "/keyfeel/#buy";
const RECOVER = "/recover/";

const { handler, sendDueReminders, setupEmail, reminderEmail } = createTrialReminder({
  app: "Keyfeel",
  slug: "keyfeel",
  fnName: "keyfeel-reminder",
  store: "kf-trial-reminders",
  tokenStore: "kf-trial-reminder-tokens",
  products: ["keyfeel", "app-suite"],

  setup: (link) => ({
    subject: "Keyfeel: getting started",
    text:
      `Thanks for trying Keyfeel. The one step that decides whether it works is the Input Monitoring permission. The first time you open Keyfeel, macOS asks you to allow it under System Settings, Privacy & Security, Input Monitoring. Without that permission Keyfeel cannot hear your keyboard and stays silent. You can switch it off again in the same place at any time.\n\n` +
      `Keyfeel uses the key code, which says which key was pressed, and never the characters you type. It sends nothing you type anywhere, and macOS does not deliver keystrokes from password fields to it.\n\n` +
      `Once it is making sound:\n` +
      `1. Try the three recorded profiles, Tactile, Cherry MX Brown and Dome, from the menu bar and keep the one you like.\n` +
      `2. Choose the apps where Keyfeel stays silent. It also goes quiet by itself while the microphone is in use, so key sounds are not played into a call.\n\n` +
      `Each setting is described on the Keyfeel page:\n${link(PAGE)}\n\n` +
      `The trial is the complete app for seven days from the first time you open it, with no account. After that you need a license key. If you buy, the key comes in your receipt email and goes into the same copy, so there is no second download. I will send one more short note around day ${REMIND_AFTER_DAYS}, and then nothing.\n\n` +
      `Questions: reply to this email and I will answer.\n\nBenjamin Ampel`,
    html:
      `<p>Thanks for trying Keyfeel. The one step that decides whether it works is the Input Monitoring permission. The first time you open Keyfeel, macOS asks you to allow it under System Settings, Privacy &amp; Security, Input Monitoring. Without that permission Keyfeel cannot hear your keyboard and stays silent. You can switch it off again in the same place at any time.</p>` +
      `<p>Keyfeel uses the key code, which says which key was pressed, and never the characters you type. It sends nothing you type anywhere, and macOS does not deliver keystrokes from password fields to it.</p>` +
      `<p>Once it is making sound:</p>` +
      `<ol><li>Try the three recorded profiles, Tactile, Cherry MX Brown and Dome, from the menu bar and keep the one you like.</li>` +
      `<li>Choose the apps where Keyfeel stays silent. It also goes quiet by itself while the microphone is in use, so key sounds are not played into a call.</li></ol>` +
      `<p>Each setting is described on <a href="${link(PAGE)}">the Keyfeel page</a>.</p>` +
      `<p>The trial is the complete app for seven days from the first time you open it, with no account. After that you need a license key. If you buy, the key comes in your receipt email and goes into the same copy, so there is no second download. I will send one more short note around day ${REMIND_AFTER_DAYS}, and then nothing.</p>` +
      `<p>Questions: reply to this email and I will answer.</p><p>Benjamin Ampel</p>`,
  }),

  reminder: (link) => ({
    subject: "Your Keyfeel trial",
    text:
      `The Keyfeel trial runs seven days from the first time you open the app, so if you have been trying it this week it ends soon. When it ends Keyfeel asks for a license key; nothing is charged.\n\n` +
      `If you want to keep it, Keyfeel is a single $9.99 payment, for life, with every update included and a 14-day refund:\n${link(BUY)}\n\n` +
      `Your license key arrives in the receipt email and is shown on the page after you pay. Choose Enter License Key in Keyfeel and paste it into the copy you already have. It works offline and needs no second download. If you lose the key, the Find a purchase page sends it again:\n${link(RECOVER)}\n\n` +
      `If Keyfeel was not for you, I would like to know why. Reply to this email with one line.\n\nBenjamin Ampel`,
    html:
      `<p>The Keyfeel trial runs seven days from the first time you open the app, so if you have been trying it this week it ends soon. When it ends Keyfeel asks for a license key; nothing is charged.</p>` +
      `<p>If you want to keep it, <a href="${link(BUY)}">Keyfeel is a single $9.99 payment</a>, for life, with every update included and a 14-day refund.</p>` +
      `<p>Your license key arrives in the receipt email and is shown on the page after you pay. Choose Enter License Key in Keyfeel and paste it into the copy you already have. It works offline and needs no second download. If you lose the key, <a href="${link(RECOVER)}">the Find a purchase page</a> sends it again.</p>` +
      `<p>If Keyfeel was not for you, I would like to know why. Reply to this email with one line.</p><p>Benjamin Ampel</p>`,
  }),
});

export { sendDueReminders, setupEmail, reminderEmail };
export default handler;
