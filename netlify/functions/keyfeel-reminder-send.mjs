// Daily at 14:20 UTC: send the Keyfeel trial reminders that are due. See keyfeel-reminder.mjs.
import { sendDueReminders } from "./keyfeel-reminder.mjs";

export default async function handler() {
  const result = await sendDueReminders();
  console.log("keyfeel-reminder-send", JSON.stringify(result));
  return new Response(JSON.stringify(result), { status: 200, headers: { "Content-Type": "application/json", "Cache-Control": "no-store" } });
}

export const config = { schedule: "20 14 * * *" };
