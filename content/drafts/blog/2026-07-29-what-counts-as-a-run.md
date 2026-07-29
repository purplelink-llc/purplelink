# What counts as a run when the tool never calls the server

The Purplelink stats dashboard tracks which tools get used by recording a run whenever a tool calls the backend. That covers 7 of the current tools. They all call the same backend service, and the instrumentation lives in a wrapper around that fetch call. One piece of code, all seven tools counted automatically.

Two tools were invisible: the citation generator and the LaTeX table generator. Both compute entirely in the browser. No network call, nothing to intercept. From the stats page's perspective, a visit to either tool looked identical to loading any other page.

The fix itself was small: fire a usage event on use, the same event the backend wrapper fires. The harder problem was defining use.

For the citation generator, the definition fell out naturally from how the tool works. It has two entry points: a DOI lookup and a manual entry form. Submitting either is a deliberate action: you're asking for a citation. Two DOI lookups count as two runs, the same way two backend requests do.

The LaTeX table generator was different. It regenerates the output on every input event: every keystroke in the data field, every change to the delimiter or alignment settings. Counting each regeneration would mean counting typing. A 90-second editing session might produce 40 or 50 events, none of which individually signals use.

What "a run" means for a table generator is closer to: the user got output worth doing something with. The rule I settled on: count once per page visit, the first time the output field contains real content. Additional edits don't add to the count. Clicking Run again doesn't add a second. The count ends up reflecting visits where the tool produced something, not visits where someone was mid-edit.

The underlying question is what we're actually trying to measure. For the citation generator, the metric is output volume: how many citations were generated. Per-action counting answers that. For the table generator, it's adoption: how many people used the tool and got something out of it. Per-session counting answers that.

Neither question was apparent before looking at how the tools work. The citation generator is built around DOI lookup because most people already have a DOI; the manual form is the fallback. The table generator is built around iteration: paste data, see output, adjust a setting, see it update. The interaction contracts are different, and they need different definitions of use to produce meaningful numbers.

The word counter and a few other client-side tools still show as page views on the dashboard. Same underlying problem. I haven't settled on what "a run" means for a word counter -- when you paste text? when you copy the output? It's a smaller question, but it's still the same question.

## LinkedIn Post

The Purplelink stats dashboard records a tool run by wrapping the backend API call. That works for every tool that calls a server. The citation generator and the LaTeX table generator both compute entirely in the browser, so from the dashboard's perspective, they were indistinguishable from page views.

Fixing the tracking was straightforward. Deciding what to track was not. For the citation generator, a run means a deliberate action: a DOI lookup or a manual form submission. Two citations count as two runs. For the LaTeX table generator, the tool regenerates on every keystroke, so counting each generation would mean counting typing. It counts once per visit, the first time real output appears.

The same question comes up for every client-side tool. The answer depends on what the tool actually does, not just how it's built.

https://purplelink.llc/blog/what-counts-as-a-run/
