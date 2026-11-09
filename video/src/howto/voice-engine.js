// The how-to narration switch (2026-11-09). Off by default: the how-tos keep the current voice (Kokoro bf_emma).
// On means narrate.py runs with TTS_ENGINE=vibevoice (the stored narrator voice, cloned with VibeVoice-1.5B), and a
// failed take falls back to the current voice for the whole video. Turn it on with HOWTO_TTS_ENGINE=vibevoice for one
// run, or for the daily job by writing "vibevoice" into ~/.config/purplelink/howto-voice-engine. Only the how-tos
// read this; every other video calls narrate.py without it.
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

export const SWITCH_FILE = path.join(os.homedir(), ".config", "purplelink", "howto-voice-engine");

export function howtoVoiceEngine(env = process.env, file = SWITCH_FILE) {
  let v = (env.HOWTO_TTS_ENGINE || "").trim().toLowerCase();
  if (!v) {
    try { v = fs.readFileSync(file, "utf8").trim().toLowerCase(); } catch { v = ""; }
  }
  return v === "vibevoice" ? "vibevoice" : "default";
}

// env for narrate.py: unchanged unless the switch is on
export function narrateEnv(env = process.env, file = SWITCH_FILE) {
  if (howtoVoiceEngine(env, file) === "vibevoice") return { ...env, TTS_ENGINE: "vibevoice" };
  const off = { ...env };
  if ((off.TTS_ENGINE || "").trim().toLowerCase() === "vibevoice") delete off.TTS_ENGINE; // off means off
  return off;
}
