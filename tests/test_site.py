from html.parser import HTMLParser
from pathlib import Path
import re
from urllib.parse import urlparse
import unittest


ROOT = Path(__file__).resolve().parents[1]
HTML_FILES = ["index.html", "privacy.html", "terms.html", "data-deletion.html"]
IDENTITY = [
    "Stark Paid Media",
    "Stark Paid Media · 21Shift",
    "21Shift SpA",
    "info@21shift.com",
    "Chile",
]
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
        self.tags = []
        self.resources = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        self.tags.append(tag)
        if tag == "a" and values.get("href"):
            self.links.append(values["href"])
        if tag == "link" and (values.get("rel") or "").lower() == "stylesheet":
            self.stylesheets.append(values.get("href"))

        resource_tags = {
            "audio",
            "embed",
            "iframe",
            "img",
            "input",
            "object",
            "script",
            "source",
            "track",
            "video",
        }
        if tag in resource_tags:
            for attribute in ["data", "poster", "src", "srcset"]:
                if values.get(attribute):
                    self.resources.append(values[attribute])

        resource_link_relations = {
            "dns-prefetch",
            "icon",
            "manifest",
            "modulepreload",
            "preconnect",
            "prefetch",
            "preload",
            "stylesheet",
        }
        if tag == "link" and values.get("href"):
            relations = set((values.get("rel") or "").lower().split())
            if relations & resource_link_relations:
                self.resources.append(values["href"])


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

    def test_privacy_discloses_credential_storage_and_lifecycle(self):
        content = read("privacy.html")
        for value in [
            "access tokens",
            "authentication credentials",
            "stored locally in protected configuration",
            "only while operationally necessary",
            "revoked or rotated",
            "access ends",
            "security requires it",
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

    def test_deletion_separates_asset_removal_from_token_revocation(self):
        content = read("data-deletion.html")
        self.assertIn("remove assigned Pages or ad accounts", content)
        self.assertIn("remove the System User or app assignment", content)
        self.assertIn("Meta's supported token-revocation controls", content)
        self.assertNotIn("revoke relevant access tokens in Meta Business Settings", content)

    def test_pages_have_no_scripts_or_forms(self):
        for name in HTML_FILES:
            parser = LinkParser()
            parser.feed(read(name))
            self.assertNotIn("script", parser.tags, name)
            self.assertNotIn("form", parser.tags, name)

    def test_pages_have_no_external_or_unexpected_resource_dependencies(self):
        for name in HTML_FILES:
            parser = LinkParser()
            parser.feed(read(name))
            for link in parser.links:
                self.assertNotIn(
                    urlparse(link).scheme.lower(),
                    {"data", "javascript", "vbscript"},
                    f"executable link {link!r} in {name}",
                )
            for resource in parser.resources:
                parsed = urlparse(resource)
                self.assertFalse(
                    resource.startswith("//") or parsed.scheme in {"http", "https"},
                    f"external resource {resource!r} in {name}",
                )
                self.assertEqual("styles.css", resource, f"unexpected resource in {name}")

        site_source = "\n".join(read(name) for name in [*HTML_FILES, "styles.css"])
        self.assertNotIn("@import", site_source.lower())
        self.assertIsNone(re.search(r"url\s*\(", site_source, re.IGNORECASE))

    def test_site_has_no_analytics_or_cookie_integrations(self):
        combined = "\n".join(read(name) for name in [*HTML_FILES, "styles.css"]).lower()
        for marker in [
            "analytics.js",
            "connect.facebook.net",
            "cookie_consent",
            "cookieconsent",
            "document.cookie",
            "fbq(",
            "ga(",
            "google-analytics",
            "googletagmanager",
            "gtag(",
            "mixpanel",
            "plausible.io",
            "posthog",
            "segment.com",
            "set-cookie",
            "umami",
        ]:
            self.assertNotIn(marker, combined)

    def test_site_has_no_build_or_runtime_dependency_manifests(self):
        for name in [
            "Gemfile",
            "Pipfile",
            "package-lock.json",
            "package.json",
            "pnpm-lock.yaml",
            "pyproject.toml",
            "requirements.txt",
            "yarn.lock",
        ]:
            self.assertFalse((ROOT / name).exists(), name)


if __name__ == "__main__":
    unittest.main()
