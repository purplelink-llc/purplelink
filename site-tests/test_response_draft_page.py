"""Response letter drafting ($24, product response-draft): the upload page sends exactly the fields the backend's
POST /response-review/draft/submit reads, the page is reachable from the Response Review page and the workflow card,
and the status page knows the product."""
import re
import unittest

from common import EMOJI, read, read_site

PAGE = "tools/response-review/draft/upload/index.html"
JS = "tools/response-review/draft/upload.js"


def submit_signature():
    app = read("backend/app.py")
    i = app.index('@api.post("/response-review/draft/submit")')
    sig = app[i:app.index("):", i)]
    return set(re.findall(r"^\s+(\w+): [^=\n]+= (?:Form|File)\(", sig, re.M))


def js_fields():
    return re.findall(r'name: "(\w+)",\s+elementId: "([\w-]+)",\s+required: (true|false)', read_site(JS))


class ResponseDraftPage(unittest.TestCase):
    def test_fields_match_the_backend_endpoint(self):
        names = {n for n, _, _ in js_fields()} | {"token"}
        self.assertEqual(names, submit_signature())

    def test_original_required_revised_optional(self):
        req = {n: r == "true" for n, _, r in js_fields()}
        self.assertTrue(req["file"])
        self.assertTrue(req["reviewer_comments"])
        self.assertFalse(req["revised_file"])
        self.assertFalse(req["author_notes"])

    def test_page_has_every_element_the_script_needs(self):
        page = read_site(PAGE)
        for name, el, _ in js_fields():
            self.assertIn(f'id="{el}"', page, el)
            if name in ("file", "revised_file"):
                self.assertIn(f'id="{el}-zone"', page)
                self.assertIn(f'id="{el}-name"', page)
        self.assertIn('"response-draft"', read_site(JS))
        self.assertIn('"/response-review/draft/submit"', read_site(JS))
        self.assertIn('/tools/response-review/draft/upload.js', page)

    def test_page_is_noindex_with_no_inline_style_or_emoji(self):
        page = read_site(PAGE)
        self.assertIn('content="noindex, nofollow"', page)
        self.assertNotRegex(page, r'\sstyle="')
        self.assertIsNone(EMOJI.search(page))
        self.assertIn("placeholder", page.lower())  # says what happens without a revised PDF

    def test_checkout_success_path_is_this_page(self):
        self.assertRegex(read("netlify/functions/checkout.mjs"),
                         r'"response-draft":[^\n]*successPath: "/tools/response-review/draft/upload/"')
        self.assertNotIn("RESPONSE_DRAFT_OPEN", read("netlify/functions/checkout.mjs"))

    def test_entry_points(self):
        landing = read_site("tools/response-review/index.html")
        self.assertRegex(landing, r'<button[^>]*data-checkout[^>]*data-product="response-draft"')
        self.assertIn("button[data-checkout]", read_site("tools/paper-review/paid-tool-landing.js"))
        workflow = read_site("tools/paper-review/index.html")
        self.assertRegex(workflow, r'data-response-draft>[^<]*<a href="/tools/response-review/#draft">')
        self.assertIn('id="draft"', landing)

    def test_status_page_knows_the_product(self):
        status = read_site("tools/paper-review/status.js")
        self.assertIn('"response-draft": {', status)
        for stage in ("extracting", "drafting", "panel"):
            self.assertIn(f'progress.stage = "{stage}"' if stage != "extracting" else 'stage="extracting"',
                          read("backend/latextools/response_draft.py"))


if __name__ == "__main__":
    unittest.main()
