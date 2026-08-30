import json
import re
import unittest
from pathlib import Path
from urllib.parse import unquote


PROJECT_ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE_ROOT = PROJECT_ROOT / "knowledge"


class PublicKnowledgeTests(unittest.TestCase):
    def test_manifest_points_to_enabled_public_documents(self):
        manifest = json.loads((KNOWLEDGE_ROOT / "sources.json").read_text(encoding="utf-8"))

        self.assertGreaterEqual(len(manifest["sources"]), 5)
        self.assertEqual(len({source["id"] for source in manifest["sources"]}), len(manifest["sources"]))

        for source in manifest["sources"]:
            self.assertTrue(source["public"])
            self.assertTrue(source["enabled"])
            self.assertTrue((KNOWLEDGE_ROOT / source["path"]).is_file())

    def test_curated_documents_do_not_contain_contact_details(self):
        contact_patterns = (
            re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
            re.compile(r"\+?\d[\d\s().-]{7,}\d"),
        )

        for document in (KNOWLEDGE_ROOT / "public").rglob("*.md"):
            content = document.read_text(encoding="utf-8")
            for pattern in contact_patterns:
                self.assertIsNone(pattern.search(content), f"Contact detail found in {document.name}")

    def test_education_facts_are_kept_out_of_the_general_profile_source(self):
        profile = (KNOWLEDGE_ROOT / "public" / "background.md").read_text(encoding="utf-8")
        education = (KNOWLEDGE_ROOT / "public" / "education.md").read_text(encoding="utf-8")

        self.assertNotIn("8.36", profile)
        self.assertNotIn("Maharana Mewar", profile)
        self.assertNotIn("St. Paul's School", profile)
        self.assertIn("8.36", education)
        self.assertIn("Maharana Mewar", education)

    def test_local_citation_links_target_existing_portfolio_content(self):
        manifest = json.loads((KNOWLEDGE_ROOT / "sources.json").read_text(encoding="utf-8"))
        template = (PROJECT_ROOT / "templates" / "index.html").read_text(encoding="utf-8")
        known_routes = {"/cardio", "/mobility"}

        for source in manifest["sources"]:
            urls = [source["url"]]
            if "demo_url" in source:
                self.assertIn("demo_label", source, f"Missing demo label for {source['id']}")
                self.assertTrue(source["demo_label"].strip(), f"Empty demo label for {source['id']}")
                urls.append(source["demo_url"])

            for url in urls:
                if url.startswith("/static/"):
                    asset = PROJECT_ROOT / "static" / unquote(url.removeprefix("/static/"))
                    self.assertTrue(asset.is_file(), f"Missing citation asset for {source['id']}")
                elif url.startswith("/#"):
                    section_id = url.removeprefix("/#")
                    self.assertIn(f'id="{section_id}"', template)
                elif url.startswith("/"):
                    self.assertIn(url, known_routes, f"Unknown local citation URL for {source['id']}")


if __name__ == "__main__":
    unittest.main()
