import unittest
from pathlib import Path

from rag.diagnostics import capture_rag_trace
from rag.query_hints import ApprovedSourceQueryHints
from rag.sources import SourceRegistry


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class ApprovedSourceQueryHintsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        registry = SourceRegistry.from_file(PROJECT_ROOT / "knowledge" / "sources.json")
        cls.hints = ApprovedSourceQueryHints.from_registry(PROJECT_ROOT / "knowledge", registry)

    def test_docker_question_guides_file_search_to_fleet_source(self):
        hints = self.hints.for_question("Which project uses Docker?")

        self.assertGreaterEqual(len(hints), 1)
        self.assertIn("Fleet Smart Vehicle Digital Twin Prototype", hints[0])
        self.assertIn("docker", hints[0])
        self.assertNotIn("Docker Compose", hints[0])

    def test_react_question_guides_file_search_to_fleet_source(self):
        hints = self.hints.for_question("Which project has React as a tool?")

        self.assertGreaterEqual(len(hints), 1)
        self.assertIn("Fleet Smart Vehicle Digital Twin Prototype", hints[0])
        self.assertIn("react", hints[0])

    def test_router_rewritten_follow_up_guides_file_search_to_fleet_source(self):
        hints = self.hints.for_question("Which Docker Compose services does the Fleet project declare?")

        self.assertGreaterEqual(len(hints), 1)
        self.assertIn("Fleet Smart Vehicle Digital Twin Prototype", hints[0])

    def test_single_character_typo_can_match_a_distinctive_reviewed_alias(self):
        source_ids = self.hints.source_ids_for_question("Which project uses Doker?")

        self.assertEqual(source_ids, ("project-digital-twin-fleet",))

    def test_networking_is_guided_to_network_projects_not_fleet(self):
        hints = self.hints.for_question("Which of Mihir's projects is related to networking?")

        rendered = "\n".join(hints)
        self.assertIn("5G Mobility Risk Prediction and Handover Decision Support", rendered)
        self.assertIn("Closed Loop SLA Violation Simulation", rendered)
        self.assertNotIn("Fleet Smart Vehicle Digital Twin Prototype", rendered)

    def test_unknown_term_leaves_file_search_unhinted(self):
        hints = self.hints.for_question("Which project uses PostgreSQL?")

        self.assertEqual(hints, ())

    def test_private_question_has_no_source_navigation_hint(self):
        self.assertEqual(self.hints.for_question("What is Mihir's phone number?"), ())

    def test_diagnostic_exposes_only_approved_keyword_and_source_hints(self):
        with capture_rag_trace() as trace:
            self.hints.for_question("Which project uses Docker?")

        event = next(item for item in trace.events if item["event"] == "query_hints.selected")
        self.assertEqual(event["approved_terms"], "docker")
        self.assertIn("Fleet Smart Vehicle", event["source_titles"])
        self.assertNotIn("Which project", str(event))

    def test_named_project_takes_precedence_over_broad_capability(self):
        hints = self.hints.for_question("How does the Fleet project use networking?")

        self.assertEqual(len(hints), 1)
        self.assertIn("Fleet Smart Vehicle Digital Twin Prototype", hints[0])

    def test_profile_alias_selects_the_general_profile_source(self):
        source_ids = self.hints.source_ids_for_question("Tell me everything about Mihir Lakhani.")

        self.assertEqual(source_ids, ("portfolio-background",))

    def test_personal_and_hobby_questions_select_the_general_profile_source(self):
        self.assertEqual(
            self.hints.source_ids_for_question("Tell me about him as a person."),
            ("portfolio-background",),
        )
        self.assertEqual(
            self.hints.source_ids_for_question("What are his hobbies?"),
            ("portfolio-background",),
        )

    def test_explicit_education_question_selects_only_the_education_source(self):
        source_ids = self.hints.source_ids_for_question("What is Mihir's CGPA?")

        self.assertEqual(source_ids, ("education-details",))

    def test_network_digital_twin_prefers_the_research_profile_over_fleet(self):
        source_ids = self.hints.source_ids_for_question(
            "Tell me about the Network Digital Twin internship."
        )

        self.assertEqual(source_ids, ("portfolio-background",))

    def test_rag_project_alias_selects_its_approved_project_source(self):
        source_ids = self.hints.source_ids_for_question(
            "Show the architecture of the Source-Cited RAG Assistant."
        )

        self.assertEqual(source_ids, ("project-source-cited-rag-assistant",))

    def test_nokia_recognition_selects_the_awards_source_not_the_internship_profile(self):
        source_ids = self.hints.source_ids_for_question(
            "What recognition is listed for Nokia Campus Connect 2025?"
        )

        self.assertEqual(source_ids, ("certifications-and-awards",))


if __name__ == "__main__":
    unittest.main()
