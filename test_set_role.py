"""Unit tests for the LLMSetRole shared core.

Pure logic, no ComfyUI required.
Run: python -m unittest test_set_role -v
"""

import os
import tempfile
import unittest

import role_core as core


class TestParseTitle(unittest.TestCase):
    def test_html_title_extracted_and_stripped(self):
        text = "<!-- title: Summarizer -->\n# RULE\nbody line\n"
        title, body = core.parse_title(text, "whatever.md")
        self.assertEqual(title, "Summarizer")
        self.assertEqual(body, "# RULE\nbody line\n")

    def test_title_case_insensitive_marker(self):
        title, body = core.parse_title("<!--   TITLE:  Foo Bar  -->\nx", "f.md")
        self.assertEqual(title, "Foo Bar")
        self.assertEqual(body, "x")

    def test_no_title_uses_prettified_filename(self):
        text = "# CRITICAL OUTPUT RULE\nprose"
        title, body = core.parse_title(text, "professional_photo.md")
        self.assertEqual(title, "Professional Photo")
        self.assertEqual(body, text)

    def test_heading_is_not_treated_as_title(self):
        # Files that begin with a '#' heading must not turn it into the title.
        title, _ = core.parse_title("# CRITICAL OUTPUT RULE\nx", "selfie_photo.md")
        self.assertEqual(title, "Selfie Photo")


class TestPrettify(unittest.TestCase):
    def test_underscores_and_hyphens(self):
        self.assertEqual(core.prettify_filename("professional_photo.md"), "Professional Photo")
        self.assertEqual(core.prettify_filename("film-noir.md"), "Film Noir")


class TestResolveSecurity(unittest.TestCase):
    def test_reject_path_separator(self):
        with self.assertRaises(ValueError):
            core.load_role_text("../secret.md")

    def test_reject_nested_path(self):
        with self.assertRaises(ValueError):
            core.load_role_text("sub/dir.md")

    def test_unknown_label_raises(self):
        with self.assertRaises(ValueError):
            core.resolve_filename("Definitely Not A Real Role")

    def test_no_roles_sentinel_raises(self):
        with self.assertRaises(ValueError):
            core.resolve_filename(core.NO_ROLES_LABEL)


class TestMissingFile(unittest.TestCase):
    def test_load_missing_raises(self):
        core._load_cached.cache_clear()
        with self.assertRaises(FileNotFoundError):
            core.load_role_text("does_not_exist_12345.md")


class TestCollisionDisambiguation(unittest.TestCase):
    def test_same_title_gets_filename_suffix(self):
        with tempfile.TemporaryDirectory() as d:
            for name in ("a.md", "b.md"):
                with open(os.path.join(d, name), "w", encoding="utf-8") as f:
                    f.write("<!-- title: Same -->\nbody")
            orig_dir = core.ROLES_DIR
            core.ROLES_DIR = d
            core._load_cached.cache_clear()
            try:
                labels = [lbl for lbl, _ in core.list_roles()]
            finally:
                core.ROLES_DIR = orig_dir
                core._load_cached.cache_clear()
        self.assertEqual(labels, ["Same (a.md)", "Same (b.md)"])


class TestHotReload(unittest.TestCase):
    def test_edit_picked_up_via_mtime(self):
        # Regression: a content edit must not return a stale cached body.
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "s.md")
            orig_dir = core.ROLES_DIR
            core.ROLES_DIR = d
            core._load_cached.cache_clear()
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.write("<!-- title: S -->\nfirst")
                os.utime(path, (1000, 1000))
                _, body1 = core.load_role_text("s.md")

                with open(path, "w", encoding="utf-8") as f:
                    f.write("<!-- title: S -->\nsecond")
                os.utime(path, (2000, 2000))
                _, body2 = core.load_role_text("s.md")
            finally:
                core.ROLES_DIR = orig_dir
                core._load_cached.cache_clear()
        self.assertEqual(body1, "first")
        self.assertEqual(body2, "second")


class TestBadEncoding(unittest.TestCase):
    def test_non_utf8_file_does_not_crash(self):
        # A mis-encoded file must not crash the dropdown build.
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "bad.md"), "wb") as f:
                f.write(b"<!-- title: Bad -->\n\xff\xfe body")
            orig_dir = core.ROLES_DIR
            core.ROLES_DIR = d
            core._load_cached.cache_clear()
            try:
                labels = [lbl for lbl, _ in core.list_roles()]
                body, _ = core.apply_role("Bad")
            finally:
                core.ROLES_DIR = orig_dir
                core._load_cached.cache_clear()
        self.assertEqual(labels, ["Bad"])
        self.assertIn("body", body)


class TestResolve(unittest.TestCase):
    def _make(self, d, names):
        for n in names:
            with open(os.path.join(d, n), "w", encoding="utf-8") as f:
                f.write(f"<!-- title: {n[:-3].upper()} -->\nbody-{n}")

    def test_resolve_returns_body_title_index(self):
        with tempfile.TemporaryDirectory() as d:
            self._make(d, ("a.md", "b.md", "c.md"))  # titles A, B, C -> positions 0,1,2
            orig = core.ROLES_DIR
            core.ROLES_DIR = d
            core._load_cached.cache_clear()
            try:
                self.assertEqual(core.resolve("A"), ("body-a.md", "A", 0))
                self.assertEqual(core.resolve("B"), ("body-b.md", "B", 1))
                self.assertEqual(core.resolve("C"), ("body-c.md", "C", 2))
            finally:
                core.ROLES_DIR = orig
                core._load_cached.cache_clear()

    def test_resolve_unknown_role_raises(self):
        with self.assertRaises(ValueError):
            core.resolve("Definitely Not A Real Role")


class TestLocalRoles(unittest.TestCase):
    """Role files are user-provided (roles/ is gitignored); validate whatever
    is installed locally instead of asserting specific bundled names."""

    def test_installed_roles_all_apply(self):
        core._load_cached.cache_clear()
        roles = core.list_roles()
        if not roles:
            self.skipTest("no role files installed in roles/")
        for label, _fn in roles:
            body, title = core.apply_role(label)
            self.assertEqual(title, label)
            self.assertTrue(body.strip(), f"role {label!r} has empty body")


if __name__ == "__main__":
    unittest.main()
