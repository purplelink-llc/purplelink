"""The evergreen articles new research can update, and the searches each one targets.

Weekly roundups never got indexed (Search Console: every one since 2026-08-31
"Discovered - currently not indexed"), while the /learn/ articles rank. So each
week's curated papers are routed into the article whose question they answer
(see evergreen.py) instead of only into a dated digest.

`queries` are real searches from Search Console (Jul-Oct 2026), not guesses;
they tell the router what a reader of that article actually asked, which is how
it decides whether a paper belongs. `scope` is what the article covers, so a
paper outside it is routed nowhere rather than forced in.

Slugs must match a folder under learn/ in the muscleonglp repo. An article
missing from this map is simply never updated.
"""
from __future__ import annotations

TOPICS: dict[str, dict] = {
    "ozempic-muscle-loss": {
        "headline": "Does Ozempic cause muscle loss? What the research actually shows",
        "scope": "How much of GLP-1 weight loss is lean mass or muscle, across semaglutide trials and body-composition studies.",
        "queries": ["does ozempic cause muscle loss", "ozempic muscle loss", "can ozempic cause muscle loss",
                    "will ozempic make you lose muscle", "does semaglutide make you lose muscle", "glp-1 muscle loss"],
    },
    "glp1-muscle-loss-statistics": {
        "headline": "GLP-1 muscle loss by the numbers",
        "scope": "Quantified lean-mass and muscle changes on GLP-1 drugs: percentages, DXA/MRI results, trial figures.",
        "queries": ["glp 1 muscle mass loss", "lean mass loss on glp-1 percentage"],
    },
    "creatine-and-ozempic": {
        "headline": "Can you take creatine with a GLP-1?",
        "scope": "Creatine supplementation alongside GLP-1 drugs: safety, kidney markers, muscle and strength evidence.",
        "queries": ["creatine and glp-1", "can you take creatine on glp 1", "creatine and zepbound",
                    "creatine and mounjaro", "creatine and semaglutide", "creatine and tirzepatide",
                    "can you take creatine while on ozempic", "creatine and retatrutide"],
    },
    "protein-on-glp1": {
        "headline": "How much protein do you actually need on a GLP-1?",
        "scope": "Daily protein targets during GLP-1 weight loss and their effect on lean mass.",
        "queries": ["how much protein do i need on ozempic", "glp 1 protein calculator", "high protein foods for glp 1"],
    },
    "glp1-protein-timing-muscle": {
        "headline": "Protein timing on a GLP-1: does when you eat protein matter for muscle?",
        "scope": "Per-meal protein distribution and timing relative to training, for people eating less on GLP-1s.",
        "queries": ["protein timing glp-1", "protein per meal muscle"],
    },
    "best-protein-for-muscle-on-glp1": {
        "headline": "Whey, plant, or collagen: the best protein for muscle on a GLP-1",
        "scope": "Protein sources and quality (whey, plant, collagen, leucine) for muscle retention during weight loss.",
        "queries": ["best protein for glp-1", "whey protein glp-1", "best protein powder for glp 1"],
    },
    "best-protein-shakes-glp1": {
        "headline": "Best protein shakes for GLP-1 users: a 5-point label checklist",
        "scope": "Protein shakes and powders for GLP-1 users: protein and leucine per serving, protein quality, tolerability, and supplement testing.",
        "queries": ["best protein powder for glp 1", "whey protein glp-1", "easy to drink protein shake for glp-1 nausea",
                    "which brands offer plant-based protein shakes suitable for glp-1 patients?"],
    },
    "glp1-high-protein-meal-plan": {
        "headline": "High-protein GLP-1 meal plan: a sample day with grams",
        "scope": "Daily protein targets turned into meals for GLP-1 users: per-meal distribution, food choices and diet patterns that preserve lean mass.",
        "queries": ["glp-1 meal plan", "high protein meal plan for ozempic", "glp 1 diet plan"],
    },
    "fuel-workouts-glp1": {
        "headline": "How to fuel workouts on a GLP-1 when you are barely hungry",
        "scope": "Eating, protein timing and hydration around resistance exercise for people on GLP-1s, including hypoglycemia risk with diabetes medications.",
        "queries": ["how to fuel workouts on glp-1", "semaglutide resistance training routine", "protein after workout glp-1"],
    },
    "glp1-vegan-vegetarian-protein": {
        "headline": "Hitting your protein target on a GLP-1 as a vegetarian or vegan",
        "scope": "Plant-based protein adequacy and quality for GLP-1 users.",
        "queries": ["vegetarian vegan glp-1", "glp-1 plant-based protein powder", "glp 1 vegan diet"],
    },
    "glp1-high-protein-meals-nausea": {
        "headline": "High-protein meals and shakes for GLP-1 nausea days",
        "scope": "GI side effects, appetite and food tolerance on GLP-1s as they affect protein intake.",
        "queries": ["meal ideas for glp-1 users nausea", "protein for nausea", "easy to drink protein shake for glp-1 nausea"],
    },
    "build-new-muscle-on-glp1": {
        "headline": "Can you build new muscle on a GLP-1, or only preserve what you have?",
        "scope": "Muscle gain (hypertrophy) during GLP-1 treatment, with training and protein.",
        "queries": ["how to build muscle on glp 1", "building muscle while on glp 1", "how to maintain muscle on glp 1"],
    },
    "best-exercises-preserve-muscle-glp1": {
        "headline": "The best exercises to preserve muscle while losing weight on a GLP-1",
        "scope": "Exercise selection and resistance-training evidence for preserving muscle during GLP-1 weight loss.",
        "queries": ["glp-1 exercise", "resistance training for glp 1", "strength training for glp 1 users"],
    },
    "beginner-resistance-training-glp1": {
        "headline": "A beginner's resistance-training plan for GLP-1 users, with a gym",
        "scope": "Training prescription (sets, reps, effort, progression) for beginners on GLP-1s.",
        "queries": ["glp1 workouts", "semaglutide resistance training routine", "glp-1 strength training protocol"],
    },
    "build-muscle-glp1-no-gym": {
        "headline": "Can you keep muscle on a GLP-1 without a gym?",
        "scope": "Home, bodyweight and band training for muscle retention on GLP-1s.",
        "queries": ["glp-1 strength training protocol at home", "ozempic workout plan pdf"],
    },
    "cardio-vs-weights-glp1": {
        "headline": "Cardio vs. weights on a GLP-1: why muscle preservation needs resistance training",
        "scope": "Aerobic versus resistance or concurrent training effects on body composition during weight loss.",
        "queries": ["cardio vs weights glp-1", "concurrent training muscle"],
    },
    "ozempic-vs-mounjaro-vs-zepbound-muscle": {
        "headline": "Ozempic vs Mounjaro vs Zepbound: which preserves more muscle?",
        "scope": "Comparisons of lean-mass outcomes between semaglutide, tirzepatide and other incretin drugs.",
        "queries": ["mounjaro vs zepbound vs ozempic", "does mounjaro cause muscle loss like ozempic", "does zepbound cause muscle loss"],
    },
    "retatrutide-muscle-loss": {
        "headline": "Retatrutide and muscle loss: what the trial data shows so far",
        "scope": "Body-composition and lean-mass data for retatrutide and other next-generation triple agonists.",
        "queries": ["retatrutide lean mass", "retatrutide muscle loss", "does retatrutide cause muscle loss"],
    },
    "muscle-after-stopping-ozempic": {
        "headline": "What happens to your muscle when you stop Ozempic?",
        "scope": "Weight regain and body composition after stopping or tapering GLP-1 drugs.",
        "queries": ["strength training after ozempic exit", "weight regain after stopping glp-1"],
    },
    "glp1-off-ramp-older-adults": {
        "headline": "Coming off a GLP-1 after 65: sarcopenia, falls, and why the plan changes",
        "scope": "Older adults on or stopping GLP-1s: sarcopenia, frailty, falls and function.",
        "queries": ["glp-1 older adults sarcopenia", "glp-1 frailty"],
    },
    "glp1-muscle-loss-women-over-50": {
        "headline": "GLP-1s and muscle loss in women over 50: why menopause changes the math",
        "scope": "Sex differences, menopause and muscle or bone during GLP-1 weight loss.",
        "queries": ["glp-1 muscle loss women over 50", "menopause glp-1 muscle"],
    },
    "glp1-bone-density-fracture-risk": {
        "headline": "GLP-1s, bone density, and fracture risk: what the evidence shows",
        "scope": "Bone mineral density and fracture outcomes on GLP-1 drugs.",
        "queries": ["glp-1 bone density", "ozempic fracture risk"],
    },
    "glp1-tendon-joint-injury-risk": {
        "headline": "GLP-1s, rapid weight loss, and tendon or joint health: what's known",
        "scope": "Tendon, ligament and joint injury signals with GLP-1 use or rapid weight loss.",
        "queries": ["glp-1 tendon injury", "glp-1 and arthritis"],
    },
    "glp1-knee-osteoarthritis-pain": {
        "headline": "GLP-1s and knee osteoarthritis pain: what the trial actually showed",
        "scope": "Osteoarthritis pain and function outcomes with GLP-1 treatment.",
        "queries": ["best glp-1 for osteoarthritis", "osteoarthritis and glp1", "glp-1 and arthritis"],
    },
    "glp1-intermittent-fasting-muscle": {
        "headline": "Intermittent fasting on a GLP-1: does it make muscle loss worse?",
        "scope": "Time-restricted eating or fasting combined with GLP-1s and its effect on lean mass.",
        "queries": ["glp 1 and intermittent fasting", "glp 1 vs fasting", "glp-1 fasting"],
    },
    "glp1-micronutrients-vitamin-d-b12-iron": {
        "headline": "The GLP-1 micronutrient checklist: vitamin D, B12, and iron",
        "scope": "Micronutrient status and deficiencies during GLP-1 treatment.",
        "queries": ["glp-1 vitamin deficiency", "ozempic b12"],
    },
    "dexa-inbody-scan-glp1": {
        "headline": "Is a DEXA or InBody scan worth it on a GLP-1?",
        "scope": "Body-composition measurement methods (DXA, BIA, MRI) used to track lean mass on GLP-1s.",
        "queries": ["dexa scan glp-1", "inbody glp-1"],
    },
    "signs-of-muscle-loss-glp1": {
        "headline": "Signs you're losing muscle, not just fat, on a GLP-1",
        "scope": "Functional and clinical signs of muscle loss: strength, grip, physical function on GLP-1s.",
        "queries": ["signs of muscle loss on ozempic", "losing muscle on ozempic"],
    },
    "ozempic-loose-skin-vs-muscle": {
        "headline": "Loose skin vs. muscle loss after GLP-1 weight loss: how to tell the difference",
        "scope": "Skin laxity and body contour after GLP-1 weight loss, versus muscle loss.",
        "queries": ["ozempic loose skin", "glp-1 loose skin", "loose skin after ozempic"],
    },
    "ozempic-body-face-muscle": {
        "headline": "\"Ozempic body,\" \"Ozempic face,\" and \"Ozempic butt\": how much is actually muscle loss?",
        "scope": "Facial and regional fat or muscle changes after GLP-1 weight loss.",
        "queries": ["ozempic face", "ozempic butt"],
    },
    "ozempic-weight-loss-plateau-muscle": {
        "headline": "GLP-1 weight-loss plateau: fat loss stalling, or muscle loss catching up?",
        "scope": "Weight-loss plateaus, metabolic adaptation and energy expenditure on GLP-1s.",
        "queries": ["glp-1 weight loss plateau", "ozempic plateau"],
    },
    "ozempic-type-2-diabetes-muscle": {
        "headline": "Ozempic for type 2 diabetes: does muscle preservation work the same as for weight loss?",
        "scope": "Muscle and body composition in people with type 2 diabetes on GLP-1s.",
        "queries": ["ozempic type 2 diabetes muscle", "semaglutide diabetes lean mass"],
    },
}


def catalog_text() -> str:
    """The article list as the router sees it: one block per slug."""
    return "\n".join(
        f"- {slug}: {t['headline']}\n  covers: {t['scope']}\n  readers search: {'; '.join(t['queries'])}"
        for slug, t in TOPICS.items()
    )
