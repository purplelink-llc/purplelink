# Checking a replication package before the data editor does

A revise-and-resubmit letter that asks for your "replication package" is really asking for nine things at once. A README with set sections. A license. Pinned software versions. One script that runs the whole pipeline. No absolute file paths left over from your laptop. A seed for anything random. Every data file the code expects. An output folder that matches the tables and figures in the paper. No debris left over from your machine. None of it is hard by itself. The hard part is noticing all nine in a project folder you've edited on and off for eight months.

Journals that require this are following a public standard, not making up a checklist. The Social Science Data Editors publish a template README, and the Data and Code Availability Standard many economics and finance journals have adopted spells out what the package itself should contain. The American Economic Association's own data editor guidance is the clearest version I've read, down to where the README belongs and how a setup script should behave. Reading any of these once is useful. Remembering all of it while you're also finishing the paper is a different problem.

I built Replication Package Checker after finding the same mistakes in my own project folders: a setwd() call pointing at /Users/ben, a stray .Rhistory file sitting in the zip, a random draw with no seed set anywhere. Drop in the .zip and it runs ten checks in the browser, reading file names and text rather than running anything. README sections. License. Pinned dependencies. An entry script or Makefile. Absolute paths, by file and line. Random seeds. Data files named in code, checked against what's actually in the package. Output folders. Leftover system files. Nothing is uploaded, and the zip never leaves the browser tab.

What matters most here is the Review label, not Pass or Fail. A missing data file might mean you forgot it, or it might mean the README correctly tells the replicator to download a large file from a separate archive. An absolute path might be a bug, or it might be the one configuration line a replicator is expected to edit before running anything. Both need a person to look. The tool's job is finding which lines deserve that look, not handing down a verdict.

What it doesn't do matters just as much. It reads file names and text, never runs the code, and can't tell you whether the output matches the numbers in your paper. Someone, ideally not whoever wrote the code, still has to run the package start to finish on a different machine. A clean report is the point where that run becomes worth someone's time, not a replacement for it.

Running this check earlier also makes the rest of pre-submission easier. A submission checklist and a camera-ready pass both assume the files underneath are already in order, and the methodology problems reviewers flag are easier to fix before those details are locked into a package you've already made public.

Further reading: Regression and Other Stories walks through the modeling choices a replicator ends up retracing through your code, with real examples of what typically goes wrong. Statistical Rethinking is a longer read, but changes how you think about what a model actually claims, worth doing before writing the README section that explains it. More books on the research desk.

Disclosure: the Amazon links above are affiliate links. As an Amazon Associate I earn from qualifying purchases.

If you have a replication package to check before a journal does, Replication Package Checker is free, and the zip never leaves your browser.

## LinkedIn Post

A "please share your replication package" request from a journal is really nine separate requirements collapsed into one sentence: a README with specific sections, a license, pinned software versions, no file paths that only exist on your laptop, a seed for anything random, and more. None of them is hard alone. Spotting all nine in a folder you've edited for eight months is the actual problem.

I built a free checker for this after catching the same mistakes in my own projects: a setwd() call pointing at my own username, a stray .Rhistory file sitting in the zip. It reads the files in your browser, nothing uploaded, and flags lines worth a second look rather than handing out a pass or fail. A missing data file might be a mistake, or it might be one your README already explains. The tool can't tell the difference. A person still has to.

Wrote up the full workflow, including what the checker deliberately does not try to do: https://purplelink.llc/blog/checking-replication-package-before-data-editor/
