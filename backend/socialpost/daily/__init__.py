"""Daily ranked social pipeline (Ben's standing approval, 2026-10-18).

candidates -> score -> compose -> vet -> queue (standing approval) -> the existing engine posts it.
There is exactly one posting path: socialpost.engine and its adapters. Nothing in this package posts.
Detection of new guides, releases and videos reuses scripts/social/events.py (the PR 219 library), see lib219.py.
"""
