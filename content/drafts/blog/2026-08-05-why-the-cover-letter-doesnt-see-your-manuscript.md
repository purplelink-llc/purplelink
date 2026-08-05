# Why the cover letter generator doesn't see your manuscript

A journal submission includes a cover letter. Writing it is one of those tasks that's annoying in proportion to how unimportant it feels relative to the manuscript you just spent months on. It needs to exist, it needs to be professional, and it needs to accurately represent what you're submitting.

The obvious design for an AI-assisted cover letter tool is: upload the PDF, extract the relevant parts, generate the letter. That's not what Purplelink's cover letter generator does. It takes the abstract and the target journal name, and nothing else.

The capability argument for this is simple. Most of what a cover letter needs is already in the abstract: the research question, the methodology, the main finding, the significance to the field. A cover letter that accurately represents those four things is a good cover letter. The manuscript adds texture and supporting detail, but the letter doesn't quote the methods section.

The privacy argument is different. A researcher uploading an unpublished manuscript to a web tool is sending that manuscript to a third-party AI service. Anthropic's API receives the input and retains it for 30 days for abuse monitoring. For most tools in this category, researchers have thought through that tradeoff and decided it's acceptable. For a cover letter, submitted before publication and often before peer review, some researchers are more cautious. The abstract is the part of the work they've already decided to make public.

Skipping the full manuscript means the tool sends roughly 250 tokens instead of several thousand. That's not a cost optimization. It reduces the surface area of unpublished IP that moves through a service the researcher doesn't fully control.

The tradeoff is real: the generated letter can only describe the manuscript at the level of detail the abstract supports. If the abstract is vague about methodology, the cover letter will be too. A researcher whose abstract says "we used machine learning techniques" gets a cover letter that says the same. That's partly fixable through the author note field, which accepts additional context, but it requires knowing the limitation exists.

The decision to build it this way also came from thinking about when cover letters actually get written. Usually it's the last few hours before a submission deadline, by someone already exhausted from manuscript preparation. Adding a PDF upload step, with parsing, preview, and error handling, adds work at exactly the wrong moment. Abstract in, letter out, under a minute.

## LinkedIn Post

Most researchers don't realize the cover letter tool never sees their manuscript. It takes only the abstract and the target journal name.

The capability argument is straightforward: a cover letter's four jobs -- state the research question, the method, the finding, the significance -- are all handled by the abstract. The manuscript adds detail the letter doesn't use.

The privacy argument is the more interesting one. Uploading an unpublished manuscript to a web tool means sending it to a third-party AI service. Anthropic retains API inputs for 30 days. For a cover letter written in the final hours before a submission deadline, some researchers are more careful about what leaves their machine. The abstract is already the public-facing summary by design.

I wrote about both sides of this, including the real tradeoff: if your abstract is vague, the letter will be too.

https://purplelink.llc/blog/why-the-cover-letter-doesnt-see-your-manuscript/
