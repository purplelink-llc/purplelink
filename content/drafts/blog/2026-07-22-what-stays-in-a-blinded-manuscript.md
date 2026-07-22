# What stays in a blinded manuscript

Most researchers know double-blind review means removing their name from the title page. The rule is simple and the fix is obvious. What catches people is everything that identifies them without using their name.

A grant number is enough. An NSF award number or NIH R01 identifier is publicly searchable. If your acknowledgements section reads "This work was supported by NSF Grant #1847293," a reviewer who knows your lab or field can look it up in a few seconds and confirm who wrote the paper. IRB protocol numbers have the same problem: they're attached to your institution in the IRB registry, and that's your institution name by another route.

Self-citations are a more subtle version. References to your own prior work are expected and often required. What identifies you is the prose around them. "In our previous work [12], we showed that..." names you without naming you. A reviewer reading a paper that cites [12] as "our previous work" and then reads [12]'s author list has found the authors. The fix is consistent: "Prior work [12] showed that..." with no possessive anywhere.

Lab-specific software is another reliable leak. If you built a tool called LabName-Toolkit and you're the only group using it, "experiments were run using LabName-Toolkit v2.1" identifies you as clearly as a byline. The same applies to GitHub repositories under your username, a lab URL, or an institutional dataset with your institution's name in the path.

The reason these leaks survive is that researchers approach blinding as a one-pass task. You take the submitted draft, search for your name, remove it from the cover page and the acknowledgements block, and submit. That covers the obvious case. The indirect identifiers (funding, protocols, citation prose, named software) require a different kind of attention because they don't trigger on a name search. You have to know what you're looking for before you can find it.

Desk rejection for anonymization failure does happen, but it's the less common outcome. More often, the breach just means the double-blind isn't blind. A reviewer who recognized you before reading the methods section is now reading with context they shouldn't have. Whether that affects their recommendation is hard to know. What's certain is that it produces a different read than the procedure intends.

The Purplelink Anonymity Check was built for this specific step: a scan that looks for all the categories that aren't your name. Author names in the body, institution mentions, funding acknowledgements, IRB identifiers, self-citation prose, named software artifacts, author-owned URLs. Each finding is quoted in context so you can see exactly what to fix. It doesn't catch everything. Figures, supplementary files, and PDF metadata each need a manual pass. But it covers the text-based leaks that are both the most common and the easiest to miss.

Running it before submission takes less time than rereading the abstract.

## LinkedIn Post

A reviewer who knows your field doesn't need your name on the title page. An NSF award number in your acknowledgements is publicly searchable. "In our previous work [12]..." followed by reference [12]'s author list is just as identifying. So is a lab-specific software package nobody else uses.

Most researchers approach blinding as a one-pass task: search for your name, remove it from the cover page. That catches the obvious case. Grant numbers, IRB protocol identifiers, citation prose, and named software artifacts don't trigger on a name search.

I wrote about the specific categories that survive the standard blind, and why the Purplelink Anonymity Check was built to catch them before submission.

https://purplelink.llc/blog/what-stays-in-a-blinded-manuscript/
