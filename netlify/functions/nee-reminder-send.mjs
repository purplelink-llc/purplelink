// Daily at 14:50 UTC: send the Née trial reminders that are due. See nee-reminder.mjs.
import { sendDueReminders } from "./nee-reminder.mjs";

export default async function handler() {
  const result = await sendDueReminders();
  console.log("nee-reminder-send", JSON.stringify(result));
  return new Response(JSON.stringify(result), { status: 200, headers: { "Content-Type": "application/json", "Cache-Control": "no-store" } });
}

export const config = { schedule: "50 14 * * *" };
