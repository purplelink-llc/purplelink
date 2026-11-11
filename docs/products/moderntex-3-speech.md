# ModernTex 3.0: read aloud and dictation (research and spike)

Status: research note, 2026-11-11. Nothing here is shipped or promised. The spike is a draft PR on the ModernTex repo
(branch `spike/read-aloud`) and must not be merged as is.

## Recommendation for 3.0

- **Read aloud: GO.** Ship it in 3.0 using Apple's on-device voices (`AVSpeechSynthesizer`) and our own LaTeX-to-speech
  converter. No model download, no new permissions, works on the current macOS 14 floor. The spike shows the approach
  works on real papers.
- **Dictation of prose: no new work.** System Dictation (Fn Fn) already types into the editor. We document it and make
  sure it behaves in our text view.
- **Spoken math dictation: NO-GO for 3.0, beta later.** It is the only part that is new value, and it is the hard part.
  Plan it as a 3.x beta on macOS 26 (`SpeechAnalyzer`) plus a rule-based spoken-math to LaTeX converter, behind a flag.

## What already exists

In ModernTex (checked in the code, 2026-11-11):

- No speech code. `EditorTextView` is an `NSTextView`, so Edit > Speech > Start Speaking already exists, but it reads
  the raw source ("backslash frac open brace x...").
- No microphone usage string and no audio-input entitlement in the app.
- The app's minimum is macOS 14. Setapp builds set `SETAPP_NO_DOWNLOADS`, which rules out downloading speech models in
  that edition.

Company assets we can reuse:

- **Tapefolio** already ships on-device speech-to-text with three engines behind one protocol: Apple `SpeechAnalyzer`
  (macOS 26), Parakeet through FluidAudio, and WhisperKit. It also has a dictation service and a custom vocabulary
  list. The transcriber protocol and the model-download and storage code can be lifted for ModernTex dictation.
- **The how-to video pipeline** has used local TTS models (Kokoro, VibeVoice, Qwen3-TTS) through Python. These are
  useful as a quality reference, but they are Python tools with multi-GB memory peaks and are not suitable to ship in
  a Mac app. Kokoro-82M is the only one small enough to consider in-app later (see options).

## Who asks for it and why

- **Accessibility.** Blind and low-vision authors use VoiceOver today, which reads LaTeX source literally. Reading
  math as words (the way Word's Read Aloud reads equations) is the feature that matters most to them.
- **RSI and motor limits.** Typing LaTeX is keyboard-heavy. Authors with RSI already use Talon, Dragon or system
  Dictation, and spoken math is the gap all of these leave.
- **Proofreading by ear.** Hearing a paragraph catches repeated words, missing words and clumsy sentences that the eye
  skips. This is the largest audience: any academic writer, no disability required. Read aloud serves it on day one.

Competitors (from web research on 2026-11-11, not each verified by hand):

- **Overleaf:** no built-in speech. People use browser extensions (dictation extensions, small "talk to LaTeX"
  projects).
- **Texifier / Texpad, TeXstudio, TeXShop:** nothing found beyond the system speech menu.
- **Word:** Read Aloud reads equations in words; Dictation works for prose. This is the bar users will compare with.
- **MathType / EquatIO:** EquatIO has speech input for math (proprietary, browser and Office).
- **Talon, Serenade:** voice coding tools; Talon is the RSI community's choice and can be scripted for LaTeX, but it is
  a separate tool with a learning curve.
- **Research:** MathBridge (arXiv 2408.07081) is a 23M-pair spoken-math to LaTeX dataset; a fine-tuned T5 reached BLEU
  about 47. MathSpeech pairs an ASR model with a 120M-parameter corrector and reports that plain Whisper large-v3 gets
  about a third of formula tokens wrong. Speech-to-LaTeX (arXiv 2508.03542) and Phoenix (arXiv 2508.07576) are recent
  follow-ups. None ships as a Mac app.

A native Mac LaTeX editor that reads math sensibly would be, as far as we found, the first one.

## On-device options

Text to speech:

| Option | Size | Latency | Licence | Notes |
| --- | --- | --- | --- | --- |
| `AVSpeechSynthesizer` (system voices) | 0 (in macOS) | starts at once | system | Premium and Enhanced voices are a user download in System Settings. Supports SSML input (`AVSpeechUtterance(ssmlRepresentation:)`), useful for pauses around math. |
| Personal Voice | 0 | starts at once | system | Needs `requestPersonalVoiceAuthorization`. Reported to fail when writing to buffers; fine for live speech. Unverified. |
| Kokoro-82M (Core ML port) | about 80 to 170 MB | well under real time on Apple silicon | Apache-2.0 | Better voice quality. Adds a download, which Setapp builds cannot do. A 3.x option, not 3.0. |

Speech to text:

| Option | Size | Latency | Licence | Notes |
| --- | --- | --- | --- | --- |
| System Dictation (Fn Fn) | 0 | live | system | Already works in any `NSTextView`. Prose only. No code needed. |
| `SpeechAnalyzer` + `SpeechTranscriber` / `DictationTranscriber` | OS-managed (installed through `AssetInventory`, not in our bundle) | live, streaming | system | macOS 26 only, about 10 languages. Supports contextual strings for custom vocabulary. Tapefolio already uses it. |
| Parakeet TDT 0.6B (FluidAudio) | about 600 MB | about 0.2 s per short utterance on M4 (vendor figure) | CC BY 4.0 (v2 English, v3 25 languages) | Tapefolio already ships it. Attribution needed. |
| Whisper large-v3-turbo (WhisperKit) | about 550 to 600 MB | about 1 s per short utterance on M4 (vendor figure) | MIT | Tapefolio already ships it. Slower than Parakeet, more languages. |

Latency and size figures are from vendor pages and model cards, not measured by us.

## Math to speech (read aloud)

Options considered:

1. **MathCAT** (Rust, MIT, about 3 MB): the best open math-to-speech rules (ClearSpeak and MathSpeak styles, about 10
   languages). Input is MathML only, so we would also need a LaTeX to MathML step (for example `pulldown-latex`, Rust,
   MIT) and a Rust build in the Swift package.
2. **Speech Rule Engine** (Apache-2.0, JavaScript): MathML in, SSML out. Would need a JavaScript runtime in the app.
3. **Our own converter in Swift** (chosen for the spike): reads the LaTeX directly, no MathML step, no new language in
   the build, about 600 lines.

The spike's converter (`ModernTexCore/LaTeXSpeech.swift`) does two things:

- **Prose:** drops markup and keeps the words; reads `\section{X}` as "Section. X."; keeps `\cite`, `\label` and `\ref`
  quiet; reads figures and tables by their caption only and skips tabular, TikZ and verbatim bodies; marks footnotes;
  reads `\%` as "percent" and `--` as "to"; skips the preamble when the whole file is selected.
- **Math:** reads in ClearSpeak-like words. `\frac{a}{b}` is "a over b"; longer fractions get "the fraction ..., over
  ..., end fraction" so the listener hears where they end. Scripts read as "x sub i", "x squared", "A inverse",
  "X transpose"; big operators as "the sum from i equals 1 to n of"; plus Greek letters, relations, roots, accents,
  `\mathbb{R}` ("the reals"). Unknown commands are read by name rather than dropped.

On the ICML template (about 30,000 characters) the converter takes under 10 ms and the output reads cleanly. Known
gaps: a dropped `\ref` or `\cite` can leave "as shown in." (a better fix is to say "reference" where no cue word comes
before it); English only; no matrices yet; no SSML pauses yet.

For 3.0 the recommendation is to keep our own converter (it is small, fast, testable and has no dependencies), and
revisit MathCAT if we add non-English speech.

## Speech to math (dictation)

System Dictation already handles prose. The new value is speaking math: "x squared plus y squared equals z squared"
should become `x^2 + y^2 = z^2`.

Approach for a later beta:

1. Transcribe with `SpeechAnalyzer` (macOS 26), with contextual strings for math words ("sub", "squared", "integral",
   Greek letters). Fall back to Parakeet where Tapefolio's code makes it cheap and the edition allows downloads.
2. Convert spoken math to LaTeX with **rules first**: the same vocabulary tables the read-aloud converter uses, run in
   reverse, with "end fraction" and "end power" as optional closers. This is deterministic, testable and on-device.
3. Only if rules prove too brittle, add a small corrector model (MathBridge-style T5 or an on-device LLM). This is a
   research project, not a 3.0 task.
4. A "math mode" toggle: speak while holding a key, insert inside `$...$` at the caret.

## Where it lives in the editor (UX)

- **3.0 read aloud:** reuse Edit > Speech > Start Speaking and Stop Speaking (and the same items in the editor's
  context menu). With nothing selected it reads the whole document; with a selection it reads that. Add a keyboard
  shortcut and a small play/stop control in the toolbar. A Settings row picks the voice and rate, and a "Read math in
  words" switch (on by default) lets people hear the raw source if they want it.
- **Highlighting:** a later step is highlighting the sentence being read, using the synthesizer's delegate callbacks
  mapped back to source ranges. The converter would need to keep a source map for this; it does not today.
- **Dictation (later):** a microphone button in the toolbar and a "Dictate Math" menu item, shown only on macOS 26.

## Risks

- **Mispronounced math erodes trust.** A wrong reading of an equation is worse than a literal one for proofreading.
  Mitigation: a large test table of formulas, a raw-source switch, and user feedback in the beta.
- **Accessibility claims.** If we market it as accessibility, VoiceOver users will judge it against Word. Ship it as
  "read aloud for proofreading" first; claim accessibility only after testing with VoiceOver users.
- **System Dictation conflicts.** Our own dictation must not fight Fn Fn. Use a separate shortcut, and stop our
  capture when system dictation starts.
- **Permissions and review.** Dictation needs `NSMicrophoneUsageDescription`, `NSSpeechRecognitionUsageDescription`
  and the hardened-runtime audio-input entitlement, plus new App Store and Setapp review text. Read aloud needs none.
- **macOS versions.** `SpeechAnalyzer` is macOS 26 only; the app supports 14. Dictation must be gated with
  `#available` and hidden on older systems.
- **Setapp edition.** No model downloads, so Setapp gets Apple engines only.
- **Localization.** New menu items, settings rows and the microphone prompt need every shipping language. The spike
  adds no strings on purpose.

## Effort estimate

- **Read aloud for 3.0:** about 2 weeks. Finish the converter (references, matrices, cases, SSML pauses, a few hundred
  test formulas), the toolbar control, shortcut, settings and localization, and a VoiceOver check.
- **Sentence highlighting:** about 1 more week (source map in the converter).
- **Spoken-math dictation beta (3.x):** about 4 to 6 weeks: transcriber reuse from Tapefolio (1 week), spoken-math
  rules and tests (2 to 3 weeks), permissions, UI, review text (1 week), beta feedback.

## The spike

- Branch `spike/read-aloud` on the ModernTex repo, draft PR, not for merge.
- Hidden flag: `defaults write com.moderntex.app moderntex.speech.readAloudLaTeX -bool YES`. With it on, Edit > Speech
  > Start Speaking in the editor reads the selection (or the file) as prose with math in words. With it off nothing
  changes.
- Files: `Sources/ModernTexCore/LaTeXSpeech.swift` (converter), `Sources/ModernTex/ReadAloudController.swift`
  (speaker and flag), two overrides in `EditorTextView.swift`, and `Tests/ModernTexTests/LaTeXSpeechTests.swift`.
- Tests use a recording mock instead of the synthesizer, so no test plays sound.

## Assumptions

- English only for the converter in 3.0.
- Apple's built-in voices are good enough for proofreading; Premium voices are a user download we can point to.
- Competitor and model figures come from public pages read on 2026-11-11 and were not each checked by hand.
