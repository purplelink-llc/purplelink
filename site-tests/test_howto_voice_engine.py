"""How-to narration (2026-11-12, Ben): VibeVoice with the stored narrator voice for every how-to, never another voice.
A take under the transcript bar is retried (up to VV_TAKES) and the best kept; a scene with no audio stops the build. No model runs here: the runner's alignment is pure Python
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

    def test_on_by_default(self):
        self.assertEqual(self.engine({}), ["vibevoice", "vibevoice"])
        self.assertEqual(self.engine({}, "vibevoice\n"), ["vibevoice", "vibevoice"])

    def test_kokoro_only_when_asked(self):
        self.assertEqual(self.engine({"HOWTO_TTS_ENGINE": "kokoro"}, "vibevoice"), ["default", None])
        self.assertEqual(self.engine({}, "kokoro\n"), ["default", None])
        self.assertEqual(self.engine({"HOWTO_TTS_ENGINE": "vibevoice"}, "kokoro"), ["vibevoice", "vibevoice"])

    def test_unknown_values_stay_on(self):
        self.assertEqual(self.engine({}, "on"), ["vibevoice", "vibevoice"])
        self.assertEqual(self.engine({"TTS_ENGINE": "edge"}), ["vibevoice", "vibevoice"])


class EngineGate(unittest.TestCase):
    def test_needs_the_env(self):
        with mock.patch.dict("os.environ", {}, clear=True):
            self.assertFalse(nar.vibevoice_on())
        with mock.patch.dict("os.environ", {"TTS_ENGINE": "kokoro"}):
            self.assertFalse(nar.vibevoice_on())

    def test_requested_but_missing_stops(self):
        with mock.patch.dict("os.environ", {"TTS_ENGINE": "vibevoice"}), \
             mock.patch.object(nar, "VV_PY", Path("/nonexistent/python")), \
             mock.patch.object(sys, "argv", ["narrate.py", str(VIDEO / "storyboards" / "howto" / "none.json")]), \
             mock.patch.object(Path, "read_text", return_value=json.dumps({"id": "t", "scenes": []})), \
             mock.patch.object(Path, "mkdir"):
            with self.assertRaises(SystemExit) as cm:
                nar.main()
        self.assertIn("not narrating with another voice", str(cm.exception.code))

    def test_bars_agree(self):
        self.assertEqual(nar.VV_MIN_MATCH, vvl.MIN_MATCH)

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


class VibeVoiceOnly(unittest.TestCase):
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

    @staticmethod
    def words(t):
        return [{"word": w.strip("."), "start": 0, "end": 0} for w in t.split()]

    def test_no_audio_after_every_take_stops_and_leaves_live_audio(self):
        calls = []

        def fake(items):
            calls.append(len(items))
            got = {}
            for t, m in items:
                if t.startswith("First"):
                    m.write_bytes(b"VV")
                    got[m] = (self.words(t), 1.0)
            return got
        with self.assertRaises(nar.VibeVoiceFailed):
            self.run_vv(fake)
        self.assertEqual(calls, [2] + [1] * (nar.VV_TAKES - 1))  # retries only the failed scene

    def test_failure_leaves_live_audio_untouched(self):
        def fake(items):
            return {}
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        out = Path(d.name)
        (out / "audio").mkdir()
        (out / "audio" / "scene-0.mp3").write_bytes(b"LIVE")
        with mock.patch.object(nar, "synth_vibevoice_batch", side_effect=fake), \
             mock.patch.object(nar, "vv_prefix", return_value="vv|x|"):
            with self.assertRaises(nar.VibeVoiceFailed):
                nar.narrate_vibevoice(self.SB, out, {}, False)
        self.assertEqual(sorted(p.name for p in (out / "audio").iterdir()), ["scene-0.mp3"])
        self.assertEqual((out / "audio" / "scene-0.mp3").read_bytes(), b"LIVE")

    def test_low_match_keeps_best_take_never_another_voice(self):
        scores = iter([0.70, 0.80, 0.75])  # scene 2's three takes; scene 0 passes first time

        def fake(items):
            got = {}
            for t, m in items:
                s = 1.0 if t.startswith("First") else next(scores)
                m.write_bytes(f"VV{s}".encode())
                got[m] = (self.words(t), s)
            return got
        scenes, out = self.run_vv(fake)
        self.assertEqual([s.get("engine") for s in scenes], ["vibevoice", None, "vibevoice"])
        self.assertEqual((out / "audio" / "scene-2.mp3").read_bytes(), b"VV0.8")
        self.assertEqual(scenes[2]["match"], 0.8)
        self.assertTrue(scenes[2]["hash"])  # kept: a rebuild reuses it
        self.assertFalse([p for p in (out / "audio").iterdir() if ".vv" in p.name])

    def test_stops_retrying_once_a_take_passes(self):
        calls = []
        scores = iter([0.5, 0.9])

        def fake(items):
            calls.append(len(items))
            got = {}
            for t, m in items:
                s = 1.0 if t.startswith("First") else next(scores)
                m.write_bytes(b"VV")
                got[m] = (self.words(t), s)
            return got
        scenes, _ = self.run_vv(fake)
        self.assertEqual(calls, [2, 1])
        self.assertEqual(scenes[2]["match"], 0.9)

    def test_success_moves_takes_into_place(self):
        def fake(items):
            got = {}
            for t, m in items:
                m.write_bytes(b"VV")
                got[m] = (self.words(t), 1.0)
            return got
        scenes, out = self.run_vv(fake)
        self.assertEqual([s.get("engine") for s in scenes], ["vibevoice", None, "vibevoice"])
        self.assertEqual((out / "audio" / "scene-2.mp3").read_bytes(), b"VV")
        self.assertFalse([p for p in (out / "audio").iterdir() if ".vv" in p.name])
        self.assertEqual(scenes[0]["words"][-1]["display"], "here.")


if __name__ == "__main__":
    unittest.main()
