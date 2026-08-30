import json
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class PortfolioEvaluationSetTests(unittest.TestCase):
    def test_starter_eval_cases_reference_only_manifest_sources(self):
        manifest = json.loads(
            (PROJECT_ROOT / "knowledge" / "sources.json").read_text(encoding="utf-8")
        )
        valid_source_ids = {source["id"] for source in manifest["sources"]}
        eval_path = PROJECT_ROOT / "evals" / "portfolio_eval.jsonl"
        cases = [
            json.loads(line)
            for line in eval_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

        self.assertGreaterEqual(len(cases), 30)
        self.assertTrue(any(not case["should_answer"] for case in cases))
        self.assertEqual(len({case["id"] for case in cases}), len(cases))
        for case in cases:
            self.assertIsInstance(case["question"], str)
            self.assertTrue(case["question"].strip())
            self.assertTrue(set(case["expected_source_ids"]).issubset(valid_source_ids))
            if "retrieval_query" in case:
                self.assertIsInstance(case["retrieval_query"], str)
                self.assertTrue(case["retrieval_query"].strip())
            if "retrieval_scope" in case:
                self.assertIn(case["retrieval_scope"], {"relevant", "all_projects"})
            if not case["should_answer"]:
                self.assertEqual(case["expected_source_ids"], [])

        all_project_case = next(case for case in cases if case["id"] == "project_catalogue_all")
        project_source_ids = {
            source["id"] for source in manifest["sources"] if source["source_type"] == "project"
        }
        self.assertEqual(set(all_project_case["expected_source_ids"]), project_source_ids)


if __name__ == "__main__":
    unittest.main()
