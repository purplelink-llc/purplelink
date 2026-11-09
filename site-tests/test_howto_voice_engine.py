"""How-to narration switch (2026-11-09): VibeVoice with the stored narrator voice is opt-in and off by default, and a
failed take puts the whole video back on the current voice. No model runs here: the runner's alignment is pure Python
and the batch call is replaced by a fake."""
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
VIDEO = ROOT / "video"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


nar = load("narrate_under_test", VIDEO / "narrate.py")
vvl = load("vibevoice_local_under_test", VIDEO / "vibevoice_local.py")


@unittest.skipUnless(shutil.which("node"), "node not installed")
class Switch(unittest.TestCase):
    def engine(self, env, file_text=None):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "howto-voice-engine"
            if file_text is not None:
                f.write_text(file_text)
            js = (f"import {{ howtoVoiceEngine, narrateEnv }} from {json.dumps(str(VIDEO / 'src/howto/voice-engine.js'))};"
                  f"const env = {json.dumps(env)}; const f = {json.dumps(str(f))};"
                  "console.log(JSON.stringify([howtoVoiceEngine(env, f), narrateEnv(env, f).TTS_ENGINE || null]));")
            out = subprocess.run(["node", "--input-type=module", "-e", js], capture_output=True, text=True, check=True)
            return json.loads(out.stdout)

    def test_off_by_default(self):
        self.assertEqual(self.engine({}), ["default", None])

    def test_file_turns_it_on(self):
        self.assertEqual(self.engine({}, "vibevoice\n"), ["vibevoice", "vibevoice"])

    def test_env_wins_over_file(self):
        self.assertEqual(self.engine({"HOWTO_TTS_ENGINE": "vibevoice"}), ["vibevoice", "vibevoice"])
        self.assertEqual(self.engine({"HOWTO_TTS_ENGINE": "kokoro"}, "vibevoice"), ["default", None])

    def test_unknown_values_and_stray_engine_stay_off(self):
        self.assertEqual(self.engine({}, "on"), ["default", None])
        self.assertEqual(self.engine({"TTS_ENGINE": "vibevoice"}), ["default", None])
        self.assertEqual(self.engine({"TTS_ENGINE": "edge"}), ["default", "edge"])

    def test_this_mac_has_the_switch_off(self):
        f = Path.home() / ".config" / "purplelink" / "howto-voice-engine"
        if f.exists():
            self.assertNotEqual(f.read_text().strip().lower(), "vibevoice", "switch is on; Ben has not turned it on")


class EngineGate(unittest.TestCase):
    def test_needs_the_env(self):
        with mock.patch.dict("os.environ", {}, clear=True):
            self.assertFalse(nar.vibevoice_on())
        with mock.patch.dict("os.environ", {"TTS_ENGINE": "kokoro"}):
            self.assertFalse(nar.vibevoice_on())

    def test_kokoro_stays_on_with_vibevoice(self):  # the fallback must still be available
        with mock.patch.dict("os.environ", {"TTS_ENGINE": "vibevoice"}):
            self.assertEqual(nar.kokoro_on(), nar.KOKORO_PY.exists() and nar.KOKORO_RUNNER.exists())

    def test_respelling_is_spoken_only(self):
        self.assertEqual(nar.spoken("Open Tapefolio and ModernTex."), "Open Tape-folio and Modern Tech.")

    def test_reference_voice_is_stored(self):
        ref = VIDEO / "voices" / "howto-narrator.wav"
        self.assertTrue(ref.exists() and ref.stat().st_size > 100_000)
        self.assertTrue((VIDEO / "voices" / "howto-narrator.txt").read_text().strip())


class Runner(unittest.TestCase):
    def test_three_sentences_per_chunk(self):
        c = vvl.chunks("One. Two? Three! Four. Five.")
        self.assertEqual(c, ["One. Two? Three!", "Four. Five."])

    def heard(self, ws):
        return [{"word": w, "start": i * 0.5, "end": i * 0.5 + 0.4} for i, w in enumerate(ws)]

    def test_align_exact(self):
        words, m = vvl.align("Open the app, then save.".split(), self.heard(["Open", "the", "app,", "then", "save."]))
        self.assertEqual(m, 1.0)
        self.assertEqual([w["word"] for w in words], ["Open", "the", "app", "then", "save"])
        self.assertEqual(words[2]["start"], 1.0)

    def test_align_keeps_one_timing_per_script_token(self):
        toks = "Tapefolio keeps every P01 file safe.".split()
        words, m = vvl.align(toks, self.heard(["Tape", "folio", "keeps", "every", "P", "0", "1", "file", "safe."]))
        self.assertEqual(len(words), len(toks))
        self.assertLess(m, 1.0)
        starts = [w["start"] for w in words]
        self.assertEqual(starts, sorted(starts))

    def test_align_interpolates_dropped_word(self):
        words, m = vvl.align("save the file now".split(), self.heard(["save", "file", "now"]))
        self.assertEqual(len(words), 4)
        self.assertAlmostEqual(m, 0.75)
        self.assertGreaterEqual(words[1]["start"], words[0]["end"])

    def test_gate_threshold(self):
        self.assertGreaterEqual(vvl.MIN_MATCH, 0.8)


class Fallback(unittest.TestCase):
    SB = {"id": "t", "scenes": [{"narration": "First line here."}, {"narration": ""}, {"narration": "Second line."}]}

    def run_vv(self, fake, live=b"KOKORO"):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        out = Path(d.name)
        (out / "audio").mkdir()
        for i in (0, 2):
            (out / "audio" / f"scene-{i}.mp3").write_bytes(live)
        with mock.patch.object(nar, "synth_vibevoice_batch", side_effect=fake), \
             mock.patch.object(nar, "vv_prefix", return_value="vv|x|"), \
             mock.patch.object(nar, "probe_duration", return_value=1.0):
            return nar.narrate_vibevoice(self.SB, out, {}, False), out

    def test_any_failure_falls_back_for_the_whole_video(self):
        calls = []

        def fake(items):
            calls.append(len(items))
            got = {}
            for t, m in items:
                if t.startswith("First"):
                    m.write_bytes(b"VV")
                    got[m] = [{"word": w, "start": 0, "end": 0} for w in t.split()]
            return got
        scenes, out = self.run_vv(fake)
        self.assertIsNone(scenes)
        self.assertEqual(calls, [2, 1])  # one retry, only for the failed scene
        self.assertEqual(sorted(p.name for p in (out / "audio").iterdir()), ["scene-0.mp3", "scene-2.mp3"])
        self.assertEqual((out / "audio" / "scene-0.mp3").read_bytes(), b"KOKORO")  # live audio untouched

    def test_success_moves_takes_into_place(self):
        def fake(items):
            got = {}
            for t, m in items:
                m.write_bytes(b"VV")
                got[m] = [{"word": w.strip("."), "start": 0, "end": 0} for w in t.split()]
            return got
        scenes, out = self.run_vv(fake)
        self.assertEqual([s.get("engine") for s in scenes], ["vibevoice", None, "vibevoice"])
        self.assertEqual((out / "audio" / "scene-2.mp3").read_bytes(), b"VV")
        self.assertFalse(list((out / "audio").glob("*.vv.mp3")))
        self.assertEqual(scenes[0]["words"][-1]["display"], "here.")


if __name__ == "__main__":
    unittest.main()
