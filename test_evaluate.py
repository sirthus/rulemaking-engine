import json
import os
import tempfile
import unittest

import evaluate_pipeline


class EvaluatePipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.corpus_dir = os.path.join(self.temp_dir.name, "corpus")
        self.gold_dir = os.path.join(self.temp_dir.name, "gold_set")
        self.output_dir = os.path.join(self.temp_dir.name, "outputs")
        os.makedirs(self.corpus_dir, exist_ok=True)
        os.makedirs(self.gold_dir, exist_ok=True)

        self.original_corpus_dir = evaluate_pipeline.CORPUS_DIR
        self.original_gold_dir = evaluate_pipeline.DEFAULT_GOLD_DIR
        self.addCleanup(self.restore_globals)
        evaluate_pipeline.CORPUS_DIR = self.corpus_dir
        evaluate_pipeline.DEFAULT_GOLD_DIR = self.gold_dir

    def restore_globals(self):
        evaluate_pipeline.CORPUS_DIR = self.original_corpus_dir
        evaluate_pipeline.DEFAULT_GOLD_DIR = self.original_gold_dir

    def write_json(self, path: str, payload):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)

    def test_alignment_metrics(self):
        docket_id = "EPA-HQ-OAR-2020-0272"
        base_dir = os.path.join(self.corpus_dir, docket_id)
        os.makedirs(base_dir, exist_ok=True)

        self.write_json(
            os.path.join(base_dir, "section_alignment.json"),
            [
                {
                    "proposed_section_id": "p1",
                    "final_section_id": "f1",
                    "match_type": "exact_heading",
                    "change_type": "modified",
                },
                {
                    "proposed_section_id": "p2",
                    "final_section_id": "f2",
                    "match_type": "exact_heading",
                    "change_type": "modified",
                },
                {
                    "proposed_section_id": "p3",
                    "final_section_id": "f3",
                    "match_type": "exact_heading",
                    "change_type": "modified",
                },
                {
                    "proposed_section_id": "p4",
                    "final_section_id": "f4",
                    "match_type": "exact_heading",
                    "change_type": "modified",
                },
                {
                    "proposed_section_id": "p5",
                    "final_section_id": "f5",
                    "match_type": "exact_heading",
                    "change_type": "unchanged",
                },
            ],
        )
        self.write_json(os.path.join(base_dir, "change_cards.json"), [])
        self.write_json(os.path.join(base_dir, "comment_themes.json"), {"clusters": []})
        self.write_json(
            os.path.join(self.gold_dir, f"{docket_id}.json"),
            {
                "docket_id": docket_id,
                "annotator": "seed",
                "annotated_at": "2026-04-05T22:05:00+00:00",
                "alignments": [
                    {
                        "proposed_section_id": "p1",
                        "final_section_id": "f1",
                        "expected_match_type": "exact_heading",
                        "expected_change_type": "modified",
                    },
                    {
                        "proposed_section_id": "p2",
                        "final_section_id": "f2",
                        "expected_match_type": "exact_heading",
                        "expected_change_type": "modified",
                    },
                    {
                        "proposed_section_id": "p3",
                        "final_section_id": "f3",
                        "expected_match_type": "exact_heading",
                        "expected_change_type": "modified",
                    },
                    {
                        "proposed_section_id": "p4",
                        "final_section_id": "f4",
                        "expected_match_type": "exact_heading",
                        "expected_change_type": "modified",
                    },
                    {
                        "proposed_section_id": "p5",
                        "final_section_id": "f5",
                        "expected_match_type": "exact_heading",
                        "expected_change_type": "added",
                    },
                ],
                "cluster_relevance": [],
            },
        )

        report = evaluate_pipeline.process_docket(docket_id, self.gold_dir, self.output_dir)

        self.assertIsNotNone(report)
        self.assertEqual(report["alignment_metrics"]["pipeline_matched"], 5)
        self.assertEqual(report["alignment_metrics"]["change_type_agreement"]["matched"], 4)
        self.assertEqual(report["alignment_metrics"]["change_type_agreement"]["pct"], 80.0)
        self.assertEqual(report["alignment_metrics"]["match_type_agreement"]["matched"], 5)

        json_path = os.path.join(self.output_dir, docket_id, "eval_report.json")
        text_path = os.path.join(self.output_dir, docket_id, "eval_report.txt")
        self.assertTrue(os.path.exists(json_path))
        self.assertTrue(os.path.exists(text_path))

        with open(json_path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        self.assertEqual(payload["schema_version"], "v1")
        self.assertEqual(payload["status"], "available")
        self.assertEqual(payload["gold_set_provenance"]["annotation_method"], "seed_derived")
        self.assertIn("alignment_metrics", payload)
        self.assertIn("cluster_relevance_metrics", payload)

    def test_cluster_relevance_metrics(self):
        docket_id = "EPA-HQ-OAR-2020-0272"
        base_dir = os.path.join(self.corpus_dir, docket_id)
        os.makedirs(base_dir, exist_ok=True)

        self.write_json(os.path.join(base_dir, "section_alignment.json"), [])
        self.write_json(
            os.path.join(base_dir, "comment_themes.json"),
            {
                "clusters": [
                    {
                        "cluster_id": "cluster-1",
                        "member_canonical_ids": ["c1", "c2"],
                    },
                    {
                        "cluster_id": "cluster-2",
                        "member_canonical_ids": ["c3"],
                    },
                    {
                        "cluster_id": "cluster-3",
                        "member_canonical_ids": ["c4"],
                    }
                ]
            },
        )
        self.write_json(
            os.path.join(base_dir, "change_cards.json"),
            [
                {
                    "card_id": "card_A",
                    "related_comments": [
                        {"comment_id": "c3", "relationship_label": "related concern present in comments"},
                        {"comment_id": "c1", "relationship_label": "related concern present in comments"}
                        ,
                        {"comment_id": "c1", "relationship_label": "related concern cited in comment"},
                        {"comment_id": "c4", "relationship_label": "related concern present in comments"}
                    ],
                },
                {
                    "card_id": "card_B",
                    "related_comments": [],
                },
            ],
        )
        self.write_json(
            os.path.join(self.gold_dir, f"{docket_id}.json"),
            {
                "docket_id": docket_id,
                "annotator": "reviewer-a",
                "annotated_at": "2026-04-06T01:00:00+00:00",
                "annotation_method": "blind_human",
                "blinded": True,
                "alignments": [],
                "cluster_relevance": [
                    {
                        "card_id": "card_A",
                        "cluster_id": "cluster-1",
                        "relevance": "relevant",
                    },
                    {
                        "card_id": "card_B",
                        "cluster_id": "cluster-1",
                        "relevance": "relevant",
                    },
                ],
            },
        )

        report = evaluate_pipeline.process_docket(docket_id, self.gold_dir, self.output_dir)

        self.assertIsNotNone(report)
        metrics = report["cluster_relevance_metrics"]
        self.assertEqual(metrics["total_gold_judgments"], 2)
        self.assertEqual(metrics["pipeline_cluster_found"], 1)
        self.assertEqual(metrics["relevant_found"], 1)
        self.assertEqual(metrics["precision_at_1"]["matched"], 1)
        self.assertEqual(metrics["precision_at_3"]["eligible_cards"], 1)
        self.assertEqual(metrics["precision_at_3"]["pct"], 100.0)

        json_path = os.path.join(self.output_dir, docket_id, "eval_report.json")
        text_path = os.path.join(self.output_dir, docket_id, "eval_report.txt")
        self.assertTrue(os.path.exists(json_path))
        self.assertTrue(os.path.exists(text_path))

        with open(json_path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        self.assertEqual(payload["schema_version"], "v1")
        self.assertEqual(payload["status"], "available")
        self.assertEqual(payload["gold_set_provenance"]["annotation_method"], "blind_human")
        self.assertTrue(payload["gold_set_provenance"]["blinded"])
        self.assertIn("alignment_metrics", payload)
        self.assertIn("cluster_relevance_metrics", payload)

    def test_missing_gold_set_writes_not_available_stub(self):
        docket_id = "EPA-HQ-OAR-2018-0225"
        base_dir = os.path.join(self.corpus_dir, docket_id)
        os.makedirs(base_dir, exist_ok=True)
        self.write_json(os.path.join(base_dir, "section_alignment.json"), [])
        self.write_json(os.path.join(base_dir, "change_cards.json"), [])
        self.write_json(os.path.join(base_dir, "comment_themes.json"), {"clusters": []})

        report = evaluate_pipeline.process_docket(docket_id, self.gold_dir, self.output_dir)

        self.assertIsNotNone(report)
        self.assertEqual(report["status"], "not_available")
        json_path = os.path.join(self.output_dir, docket_id, "eval_report.json")
        with open(json_path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        self.assertEqual(payload["schema_version"], "v1")
        self.assertEqual(payload["reason"], "no_gold_set")

    def test_invalid_gold_set_returns_none(self):
        docket_id = "EPA-HQ-OAR-2020-0272"
        base_dir = os.path.join(self.corpus_dir, docket_id)
        os.makedirs(base_dir, exist_ok=True)
        self.write_json(os.path.join(base_dir, "section_alignment.json"), [])
        self.write_json(os.path.join(base_dir, "change_cards.json"), [])
        self.write_json(os.path.join(base_dir, "comment_themes.json"), {"clusters": []})
        self.write_json(
            os.path.join(self.gold_dir, f"{docket_id}.json"),
            {
                "docket_id": docket_id,
                "annotator": "reviewer-a",
                "alignments": [{"proposed_section_id": "p1"}],
                "cluster_relevance": [],
            },
        )

        report = evaluate_pipeline.process_docket(docket_id, self.gold_dir, self.output_dir)

        self.assertIsNone(report)


if __name__ == "__main__":
    unittest.main()
