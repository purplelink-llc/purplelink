# circledhoops-bed.m4a

The same file as `apps/reels/assets/music/top10-bed.m4a` in the lockin repo: every Circled Hoops video uses it.

An original instrumental made for Circled Hoops on 2026-11-09 with ACE-Step 1.5 (MIT license,
https://github.com/ACE-Step/ACE-Step-1.5), run locally. The `acestep-v15-sft` weights are MIT as well. ACE-Step's
license puts no restriction on the audio it generates, so the track is ours to use, including in monetised social
videos. It quotes no existing theme or melody; the prompt describes a style only.

- Source take: `acestep-v15-sft` (DiT) with the `acestep-5Hz-lm` planner, text2music, seed 20261171, 50 steps,
  cfg 7.0, 95 s, 92 bpm, C minor, 4/4, instrumental.
- Re-render: the same model in cover mode on that take (cover strength 1.0, so the composition is kept), seed
  20261171, 64 steps, cfg 5.0, shift 3.0. This cleaned up the garbled texture of the source take.
- Edit: starts 10 s into the render so it opens on the action, 79 s long, 3 s fade-out, levelled to -22 LUFS,
  AAC 160 kb/s.
- Prompt: "Heroic, dramatic orchestral sports highlight underscore. Tense and driving but triumphant: a bold French
  horn section and bright trumpet fanfares calling out a strong heroic melody over relentless staccato strings,
  pounding timpani and big war drums. Minor-key tension that lifts into soaring, powerful brass fanfares. The hype
  and swagger before the big game, exciting and confident. Serious, not cute, not playful, no cheesy pop. Full
  orchestra with a big brass section and percussion. No vocals."

`mix-circledhoops.py` loops it if an ad runs long and ducks it under the narration.
