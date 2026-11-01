/**
 * Optional Lenscrib trial emails: one setup email when someone asks for it, and one reminder about five days later.
 * Nothing else, and never a list: each record is deleted when its reminder is sent. The mechanics (endpoint,
 * unsubscribe, rate limits, buyer check, retention) are in netlify/lib/trial-reminder.mjs; this file holds the
 * app's settings and the wording of the two emails, using only what the Lenscrib page says.
 *
 * POST /.netlify/functions/lenscrib-reminder             { email, website? }  (the form on /lenscrib/)
 * GET or POST /.netlify/functions/lenscrib-reminder?u=<token>                 one-click unsubscribe
 *
 * Blobs: "lcb-trial-reminders" (key: email), "lcb-trial-reminder-tokens" (key: token). The daily sender is
 * lenscrib-reminder-send.mjs. Env: RESEND_API_KEY, STRIPE_SECRET_KEY.
 *
 * There is no /lenscrib/start/ guide, so the setup email links the product page.
 */

import { createTrialReminder, REMIND_AFTER_DAYS } from "../lib/trial-reminder.mjs";

export { REMIND_AFTER_DAYS };

const PAGE = "/lenscrib/";
const BUY = "/lenscrib/#buy";
const RECOVER = "/recover/";

const { handler, sendDueReminders, setupEmail, reminderEmail } = createTrialReminder({
  app: "Lenscrib",
  slug: "lenscrib",
  fnName: "lenscrib-reminder",
  store: "lcb-trial-reminders",
  tokenStore: "lcb-trial-reminder-tokens",
  products: ["lenscrib"],

  setup: (link) => ({
    subject: "Lenscrib: getting started",
    text:
      `Thanks for trying Lenscrib. Your photos stay on your Mac: the model that writes titles, descriptions and keywords runs on the Mac, and the place and date come from the photo's own GPS and date with an offline place list. The internet is used for the one-time model download from Hugging Face (about 3 GB, the first time you use it) and the app's check for a new version. Neither carries your photos.\n\n` +
      `Three things worth knowing in the first few minutes:\n` +
      `1. The model is a large download, so the first run waits for it. That happens once.\n` +
      `2. Lenscrib is a draft writer. The model can be wrong: it guesses species and places. Read every field before you save, especially anything an editorial caption states as fact.\n` +
      `3. Lenscrib writes the metadata into your image files and exports each agency's CSV. It does not upload to Adobe Stock, Shutterstock, Alamy, Vecteezy or Dreamstime; you do that on their sites.\n\n` +
      `Each part is described on the Lenscrib page:\n${link(PAGE)}\n\n` +
      `The trial is the complete app for seven days from the first time you open it, with no account. After that you need a license key. If you buy, the key comes in your receipt email and goes into the same copy, so there is no second download. I will send one more short note around day ${REMIND_AFTER_DAYS}, and then nothing.\n\n` +
      `Questions: reply to this email and I will answer.\n\nBenjamin Ampel`,
    html:
      `<p>Thanks for trying Lenscrib. Your photos stay on your Mac: the model that writes titles, descriptions and keywords runs on the Mac, and the place and date come from the photo's own GPS and date with an offline place list. The internet is used for the one-time model download from Hugging Face (about 3 GB, the first time you use it) and the app's check for a new version. Neither carries your photos.</p>` +
      `<p>Three things worth knowing in the first few minutes:</p>` +
      `<ol><li>The model is a large download, so the first run waits for it. That happens once.</li>` +
      `<li>Lenscrib is a draft writer. The model can be wrong: it guesses species and places. Read every field before you save, especially anything an editorial caption states as fact.</li>` +
      `<li>Lenscrib writes the metadata into your image files and exports each agency's CSV. It does not upload to Adobe Stock, Shutterstock, Alamy, Vecteezy or Dreamstime; you do that on their sites.</li></ol>` +
      `<p>Each part is described on <a href="${link(PAGE)}">the Lenscrib page</a>.</p>` +
      `<p>The trial is the complete app for seven days from the first time you open it, with no account. After that you need a license key. If you buy, the key comes in your receipt email and goes into the same copy, so there is no second download. I will send one more short note around day ${REMIND_AFTER_DAYS}, and then nothing.</p>` +
      `<p>Questions: reply to this email and I will answer.</p><p>Benjamin Ampel</p>`,
  }),

  reminder: (link) => ({
    subject: "Your Lenscrib trial",
    text:
      `The Lenscrib trial runs seven days from the first time you open the app, so if you have been trying it this week it ends soon. When it ends Lenscrib asks for a license key; nothing is charged.\n\n` +
      `If you want to keep it, Lenscrib is a single $19.99 payment, with every update included and a 14-day refund:\n${link(BUY)}\n\n` +
      `Your license key arrives in the receipt email and is shown on the page after you pay. Choose Enter License Key in Lenscrib and paste it into the copy you already have. It works offline, needs no second download, and works on up to two of your Macs. If you lose the key, the Find a purchase page sends it again:\n${link(RECOVER)}\n\n` +
      `If Lenscrib was not for you, I would like to know why. Reply to this email with one line.\n\nBenjamin Ampel`,
    html:
      `<p>The Lenscrib trial runs seven days from the first time you open the app, so if you have been trying it this week it ends soon. When it ends Lenscrib asks for a license key; nothing is charged.</p>` +
      `<p>If you want to keep it, <a href="${link(BUY)}">Lenscrib is a single $19.99 payment</a>, with every update included and a 14-day refund.</p>` +
      `<p>Your license key arrives in the receipt email and is shown on the page after you pay. Choose Enter License Key in Lenscrib and paste it into the copy you already have. It works offline, needs no second download, and works on up to two of your Macs. If you lose the key, <a href="${link(RECOVER)}">the Find a purchase page</a> sends it again.</p>` +
      `<p>If Lenscrib was not for you, I would like to know why. Reply to this email with one line.</p><p>Benjamin Ampel</p>`,
  }),
});

export { sendDueReminders, setupEmail, reminderEmail };
export default handler;
