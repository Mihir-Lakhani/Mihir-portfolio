import unittest

from rag.response_intent import classify_response_intent


class ResponseIntentTests(unittest.TestCase):
    def test_normal_question_keeps_the_existing_concise_path(self):
        intent = classify_response_intent("What problem did the Fleet project solve?")

        self.assertEqual(intent.response_profile, "concise")
        self.assertEqual(intent.diagram_scope, "none")
        self.assertTrue(intent.is_default)

    def test_explicit_everything_request_selects_deep_dive_only(self):
        intent = classify_response_intent("Tell me everything about the Fleet project")

        self.assertEqual(intent.response_profile, "deep_dive")
        self.assertEqual(intent.diagram_scope, "none")

    def test_exact_mermaid_wording_selects_one_diagram(self):
        intent = classify_response_intent("mermaid diagram for fleet")

        self.assertEqual(intent.response_profile, "concise")
        self.assertEqual(intent.diagram_scope, "single")

    def test_all_diagrams_request_selects_the_full_gallery(self):
        intent = classify_response_intent("Give me all the architecture diagrams")

        self.assertEqual(intent.diagram_scope, "all")


if __name__ == "__main__":
    unittest.main()
