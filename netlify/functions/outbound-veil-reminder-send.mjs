// Daily at 14:00 UTC: send the Outbound Veil trial reminders that are due. See outbound-veil-reminder.mjs.
import { sendDueReminders } from "./outbound-veil-reminder.mjs";

export default async function handler() {
  const result = await sendDueReminders();
  console.log("outbound-veil-reminder-send", JSON.stringify(result));
  return new Response(JSON.stringify(result), { status: 200, headers: { "Content-Type": "application/json", "Cache-Control": "no-store" } });
}

export const config = { schedule: "0 14 * * *" };
