"""The free Mac wallpaper pack (/photography/wallpapers/, photo-arm idea 2, 2026-10-31).

The files are not in site/: they are served from the wallpaper-files Blobs store by wallpaper-download.mjs. These
checks keep the page, the rewrite, the render script's list and the function's name patterns in agreement, so a
renamed photograph cannot leave a download button pointing at a 404."""
import importlib.util
import re
import unittest
from common import ROOT, SITE, EMOJI, meta, read_site, sitemap_paths, has_noindex

PAGE = "photography/wallpapers/index.html"
FILES = "/photography/wallpapers/files/"


def wallpapers_script():
    spec = importlib.util.spec_from_file_location("photo_wallpapers", ROOT / "scripts" / "photo_wallpapers.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class WallpapersPage(unittest.TestCase):
    def setUp(self):
        self.html = read_site(PAGE)
        self.mod = wallpapers_script()

    def test_every_photo_has_both_sizes_and_the_packs(self):
        links = set(re.findall(r'href="' + re.escape(FILES) + r'([^"]+)"', self.html))
        want = {f"purplelink-{slug}-{size}.jpg" for _, slug, *_ in self.mod.FREE for size in self.mod.SIZES}
        want |= {f"purplelink-wallpapers-{size}.zip" for size in self.mod.SIZES}
        self.assertEqual(links, want)

    def test_names_match_the_function_patterns(self):
        fn = (ROOT / "netlify/functions/wallpaper-download.mjs").read_text()
        image = re.search(r"IMAGE_NAME = /(.+)/;", fn).group(1)
        zipn = re.search(r"ZIP_NAME = /(.+)/;", fn).group(1)
        for name in re.findall(r'href="' + re.escape(FILES) + r'([^"]+)"', self.html):
            self.assertTrue(re.fullmatch(image, name) or re.fullmatch(zipn, name), name)

    def test_sizes_are_the_ones_promised(self):
        self.assertEqual(self.mod.SIZES, {"6k": (6016, 3384), "macbook": (3456, 2234)})
        self.assertIn("6016 by 3384", self.html)
        self.assertIn("3456 by 2234", self.html)

    def test_free_pack_is_five(self):
        self.assertEqual(len(self.mod.FREE), 5)
        self.assertEqual(len({stem for stem, *_ in self.mod.FREE}), 5)

    def test_previews_and_card_exist(self):
        for src in re.findall(r'(?:src|srcset)="([^"]+)"', self.html):
            for part in src.split(","):
                path = part.strip().split(" ")[0]
                if path.startswith("/assets/"):
                    self.assertTrue((SITE / path.lstrip("/").split("?")[0]).is_file(), path)
        card = meta(self.html, "og:image").replace("https://purplelink.llc/", "")
        self.assertTrue((SITE / card).is_file(), card)

    def test_rewrite_points_at_the_function(self):
        toml = (ROOT / "netlify.toml").read_text()
        self.assertRegex(toml, r'from = "/photography/wallpapers/files/\*"\s+to = "/\.netlify/functions/wallpaper-download\?file=:splat"\s+status = 200\s+force = true')

    def test_no_email_gate_and_the_form_is_optional(self):
        # Ben chose an optional email field, not a gate: the downloads must not sit inside the form.
        form = re.search(r"<form\b.*?</form>", self.html, re.S).group(0)
        self.assertNotIn(FILES, form)
        self.assertIn('name="wallpaper-news"', form)
        self.assertIn('data-netlify="true"', form)

    def test_indexed_and_in_the_sitemap(self):
        self.assertFalse(has_noindex(self.html))
        self.assertIn("/photography/wallpapers/", sitemap_paths())

    def test_batterymeter_links_here(self):
        self.assertIn('href="/photography/wallpapers/?utm_source=batterymeter', read_site("batterymeter/index.html"))

    def test_csp_and_copy_rules(self):
        self.assertNotRegex(self.html, r"<[a-zA-Z][^>]*\sstyle\s*=")
        self.assertIsNone(EMOJI.search(self.html))
        self.assertNotIn("—", self.html)


if __name__ == "__main__":
    unittest.main()
