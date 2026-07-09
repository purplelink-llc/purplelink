"""End-to-end MuscleOnGLP flagship-guide production pipeline: draft, red
team, typeset. A one-time content-production run, not a recurring cron (see
design doc's Architecture section)."""
from pathlib import Path

from muscleonglp.draft import draft_guide
from muscleonglp.redteam import run_redteam_passes
from muscleonglp.typeset import render_guide_pdf


async def produce_guide(client, output_path: Path) -> Path:
    """Run the full pipeline and write the final PDF to *output_path*."""
    draft = await draft_guide(client)
    final_text, verdicts = await run_redteam_passes(client, draft)
    return render_guide_pdf(final_text, output_path)
