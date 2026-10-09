/**
 * Optional Tapefolio trial emails: one setup email when someone asks for it, and one reminder about five days later.
 * Nothing else, and never a list: each record is deleted when its reminder is sent. The mechanics (endpoint,
 * unsubscribe, rate limits, buyer check, retention) are in netlify/lib/trial-reminder.mjs; this file holds the
 * app's settings and the wording of the two emails, using only what the Tapefolio page says.
 *
 * POST /.netlify/functions/tapefolio-reminder             { email, website? }  (the form on /tapefolio/)
 * GET or POST /.netlify/functions/tapefolio-reminder?u=<token>                 one-click unsubscribe
 *
 * Blobs: "tf-trial-reminders" (key: email), "tf-trial-reminder-tokens" (key: token). The daily sender is
 * tapefolio-reminder-send.mjs. Env: RESEND_API_KEY, STRIPE_SECRET_KEY.
 *
 * There is no /tapefolio/start/ guide, so the setup email links the product page.
 */

import { createTrialReminder, REMIND_AFTER_DAYS } from "../lib/trial-reminder.mjs";

export { REMIND_AFTER_DAYS };

const PAGE = "/tapefolio/";
const BUY = "/tapefolio/#buy";
const RECOVER = "/recover/";

const { handler, sendDueReminders, setupEmail, reminderEmail } = createTrialReminder({
  app: "Tapefolio",
  slug: "tapefolio",
  fnName: "tapefolio-reminder",
  store: "tf-trial-reminders",
  tokenStore: "tf-trial-reminder-tokens",
  products: ["tapefolio", "app-suite"],

  setup: (link) => ({
    subject: "Tapefolio: getting started",
    text:
      `Thanks for trying Tapefolio. Your files stay on your Mac: transcription, speaker labels, identifier removal and OCR all run on the Mac. The only use of the internet is the optional model downloads inside the app, each once.\n\n` +
      `Three things worth knowing in the first few minutes:\n` +
      `1. The first run on a new Mac can take a few minutes while macOS prepares its models for the Neural Engine. That wait is normal and happens once.\n` +
      `2. One small speech model is built in, so you can start with no download. Better models are optional downloads in the app, and Settings can delete them again.\n` +
      `3. Tapefolio will mishear some words and mislabel some speakers. The review screen plays the audio beside the text with the current word highlighted, so check anything you plan to quote against the recording.\n\n` +
      `Identifier removal finds names, places, organizations, emails, phone numbers, addresses, links, ID numbers and dates of birth and replaces them with codes. It misses some. Read each one in the review step and decide whether to replace it or keep it. The key file that maps the codes back is saved in its own file, apart from the transcript, so keep it somewhere safe.\n\n` +
      `Each part is described on the Tapefolio page:\n${link(PAGE)}\n\n` +
      `The trial is the complete app for seven days from the first time you open it, with no account. After that you need a license key. If you buy, the key comes in your receipt email and goes into the same copy, so there is no second download. I will send one more short note around day ${REMIND_AFTER_DAYS}, and then nothing.\n\n` +
      `Questions: reply to this email and I will answer.\n\nBenjamin Ampel`,
    html:
      `<p>Thanks for trying Tapefolio. Your files stay on your Mac: transcription, speaker labels, identifier removal and OCR all run on the Mac. The only use of the internet is the optional model downloads inside the app, each once.</p>` +
      `<p>Three things worth knowing in the first few minutes:</p>` +
      `<ol><li>The first run on a new Mac can take a few minutes while macOS prepares its models for the Neural Engine. That wait is normal and happens once.</li>` +
      `<li>One small speech model is built in, so you can start with no download. Better models are optional downloads in the app, and Settings can delete them again.</li>` +
      `<li>Tapefolio will mishear some words and mislabel some speakers. The review screen plays the audio beside the text with the current word highlighted, so check anything you plan to quote against the recording.</li></ol>` +
      `<p>Identifier removal finds names, places, organizations, emails, phone numbers, addresses, links, ID numbers and dates of birth and replaces them with codes. It misses some. Read each one in the review step and decide whether to replace it or keep it. The key file that maps the codes back is saved in its own file, apart from the transcript, so keep it somewhere safe.</p>` +
      `<p>Each part is described on <a href="${link(PAGE)}">the Tapefolio page</a>.</p>` +
      `<p>The trial is the complete app for seven days from the first time you open it, with no account. After that you need a license key. If you buy, the key comes in your receipt email and goes into the same copy, so there is no second download. I will send one more short note around day ${REMIND_AFTER_DAYS}, and then nothing.</p>` +
      `<p>Questions: reply to this email and I will answer.</p><p>Benjamin Ampel</p>`,
  }),

  reminder: (link) => ({
    subject: "Your Tapefolio trial",
    text:
      `The Tapefolio trial runs seven days from the first time you open the app, so if you have been trying it this week it ends soon. When it ends Tapefolio asks for a license key; nothing is charged.\n\n` +
      `If you want to keep it, Tapefolio is a single $29.99 payment, with every update included and a 14-day refund:\n${link(BUY)}\n\n` +
      `Your license key arrives in the receipt email and is shown on the page after you pay. Choose Enter License Key in Tapefolio and paste it into the copy you already have. It works offline, needs no second download, and works on up to two of your Macs. If you lose the key, the Find a purchase page sends it again:\n${link(RECOVER)}\n\n` +
      `If Tapefolio was not for you, I would like to know why. Reply to this email with one line.\n\nBenjamin Ampel`,
    html:
      `<p>The Tapefolio trial runs seven days from the first time you open the app, so if you have been trying it this week it ends soon. When it ends Tapefolio asks for a license key; nothing is charged.</p>` +
      `<p>If you want to keep it, <a href="${link(BUY)}">Tapefolio is a single $29.99 payment</a>, with every update included and a 14-day refund.</p>` +
      `<p>Your license key arrives in the receipt email and is shown on the page after you pay. Choose Enter License Key in Tapefolio and paste it into the copy you already have. It works offline, needs no second download, and works on up to two of your Macs. If you lose the key, <a href="${link(RECOVER)}">the Find a purchase page</a> sends it again.</p>` +
      `<p>If Tapefolio was not for you, I would like to know why. Reply to this email with one line.</p><p>Benjamin Ampel</p>`,
  }),
});

export { sendDueReminders, setupEmail, reminderEmail };
export default handler;
