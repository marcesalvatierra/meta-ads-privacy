from html.parser import HTMLParser
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
HTML_FILES = ["index.html", "privacy.html", "terms.html", "data-deletion.html"]
IDENTITY = ["Stark Paid Media", "21Shift SpA", "info@21shift.com"]
FORBIDDEN_TEXT = [
    "Meta Ads Manager Tool",
    "marce@salvatierra.dev",
    "Create, update, and manage advertising campaigns",
    "does not persistently store Meta user data",
    "communicates exclusively with Meta's Graph API",
    "this invalidates the old one",
]


class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.stylesheets = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "a" and values.get("href"):
            self.links.append(values["href"])
        if tag == "link" and values.get("rel") == "stylesheet":
            self.stylesheets.append(values.get("href"))


def read(name):
    return (ROOT / name).read_text(encoding="utf-8")


class SiteComplianceTests(unittest.TestCase):
    def test_required_files_exist(self):
        for name in [*HTML_FILES, "styles.css"]:
            self.assertTrue((ROOT / name).is_file(), name)

    def test_identity_is_consistent(self):
        for name in HTML_FILES:
            content = read(name)
            for value in IDENTITY:
                self.assertIn(value, content, f"{value} missing from {name}")

    def test_legacy_and_inaccurate_claims_are_removed(self):
        combined = "\n".join(read(name) for name in HTML_FILES if (ROOT / name).exists())
        for value in FORBIDDEN_TEXT:
            self.assertNotIn(value, combined)

    def test_pages_use_shared_styles_and_complete_navigation(self):
        required = {"index.html", "privacy.html", "terms.html", "data-deletion.html"}
        for name in HTML_FILES:
            parser = LinkParser()
            parser.feed(read(name))
            self.assertIn("styles.css", parser.stylesheets, name)
            internal = {
                link.split("#", 1)[0]
                for link in parser.links
                if link.endswith(".html") or ".html#" in link
            }
            self.assertTrue(required.issubset(internal), f"navigation incomplete in {name}")

    def test_privacy_disclosures(self):
        content = read("privacy.html")
        for value in [
            "read-only",
            "ads_read",
            "Meta Marketing API",
            "OpenAI",
            "GitHub Pages",
            "Optional Page Messaging Module",
            "do not sell",
            "international",
        ]:
            self.assertIn(value, content)

    def test_terms_disclosures(self):
        content = read("terms.html")
        for value in [
            "Authorized Use",
            "Client Assets",
            "Third-Party Services",
            "Confidentiality",
            "Limitation of Liability",
            "Laws of Chile",
        ]:
            self.assertIn(value, content)

    def test_deletion_disclosures(self):
        content = read("data-deletion.html")
        for value in [
            "30 calendar days",
            "Do not send passwords or access tokens",
            "revoke",
            "identity and authority",
            "aggregated or de-identified",
        ]:
            self.assertIn(value, content)


if __name__ == "__main__":
    unittest.main()
