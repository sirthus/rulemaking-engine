import csv
import json
import os
import tempfile
import unittest

import generate_outputs


class Phase8Tests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.corpus_dir = os.path.join(self.temp_dir.name, "corpus")
        self.output_dir = os.path.join(self.temp_dir.name, "outputs")
        os.makedirs(self.corpus_dir, exist_ok=True)

        self.original_corpus_dir = generate_outputs.CORPUS_DIR
        self.addCleanup(self.restore_globals)
        generate_outputs.CORPUS_DIR = self.corpus_dir

    def restore_globals(self):
        generate_outputs.CORPUS_DIR = self.original_corpus_dir

    def write_json(self, path: str, payload):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)

    def test_process_docket_writes_all_output_formats(self):
        docket_id = "EPA-HQ-OAR-2020-0272"
        base_dir = os.path.join(self.corpus_dir, docket_id)
        os.makedirs(base_dir, exist_ok=True)

        self.write_json(
            os.path.join(base_dir, "comment_themes.json"),
            {
                "docket_id": docket_id,
                "total_comments": 14,
                "total_canonical_comments": 7,
                "total_clusters": 1,
                "clusters": [
                    {
                        "cluster_id": f"{docket_id}_cluster_0001",
                        "label": "Small Refinery Compliance Timeline and Costs",
                        "label_description": "Small refineries describe cost and scheduling pressure under the proposal.",
                        "canonical_count": 7,
                        "total_raw_comments": 14,
                        "member_canonical_ids": ["c1", "c2", "c3"],
                        "top_keywords": ["refinery", "cost", "compliance", "deadline"],
                        "commenter_type_distribution": {"business": 5, "individual": 2},
                    }
                ],
            },
        )
        self.write_json(
            os.path.join(base_dir, "label_run.json"),
            {
                "schema_version": "v1",
                "phase": "7",
                "runtime": "ollama",
                "model": "qwen3:14b",
                "prompt_version": "v1",
                "completed_at": "2026-04-05T18:00:00+00:00",
                "total_input_tokens": 111,
                "total_output_tokens": 22,
                "no_think": True,
            },
        )
        self.write_json(
            os.path.join(base_dir, "change_cards.json"),
            [
                {
                    "card_id": f"{docket_id}_card_0001",
                    "docket_id": docket_id,
                    "change_type": "modified",
                    "match_type": "exact_heading",
                    "heading_similarity": 0.95,
                    "proposed_section_id": "proposed_001",
                    "final_section_id": "final_001",
                    "proposed_heading": "Compliance deadlines",
                    "final_heading": "Compliance deadlines",
                    "proposed_text_snippet": "Old text",
                    "final_text_snippet": "New text",
                    "related_comments": [
                        {
                            "comment_id": "c1",
                            "relationship_label": "related concern present in comments",
                        },
                        {
                            "comment_id": "c2",
                            "relationship_label": "related concern cited in comment",
                        },
                    ],
                    "preamble_links": [
                        {
                            "preamble_section_id": "preamble_005",
                            "preamble_heading": "Response to comments",
                            "link_type": "cfr_citation",
                            "link_score": 1.0,
                            "relationship_label": "same section cited in preamble discussion",
                        }
                    ],
                    "alignment_signal": {
                        "level": "high",
                        "score": 8,
                        "features": {
                            "comment_count": 2,
                            "unique_comment_count": 1,
                            "largest_family_size": 2,
                            "best_attribution_confidence": "high",
                            "preamble_link_count": 1,
                            "best_link_type": "cfr_citation",
                        },
                        "evidence_note": "2 comments attributed; 1 preamble section linked by CFR citation.",
                    },
                    "review_status": "pending",
                }
            ],
        )
        self.write_json(
            os.path.join(base_dir, "alignment_log.json"),
            {
                "section_alignment": {
                    "proposed_count": 10,
                    "final_count": 10,
                    "matched_count": 9,
                    "coverage_pct": 90.0,
                },
            },
        )
        self.write_json(
            os.path.join(base_dir, "comment_attribution.json"),
            [
                {
                    "comment_id": "c1",
                    "classification": "substantive_inline",
                    "attribution_method": "citation",
                    "confidence": "high",
                },
                {
                    "comment_id": "c2",
                    "classification": "substantive_inline",
                    "attribution_method": "keyword",
                    "confidence": "medium",
                },
                {
                    "comment_id": "c3",
                    "classification": "substantive_inline",
                    "attribution_method": "unattributed",
                    "confidence": "none",
                }
            ],
        )

        result = generate_outputs.process_docket(docket_id, self.output_dir, force=True)

        self.assertIsNotNone(result)

        json_path = os.path.join(self.output_dir, docket_id, "report.json")
        csv_path = os.path.join(self.output_dir, docket_id, "report.csv")
        html_path = os.path.join(self.output_dir, docket_id, "report.html")

        with open(json_path, "r", encoding="utf-8") as handle:
            report = json.load(handle)

        self.assertEqual(report["schema_version"], "v1")
        self.assertEqual(report["summary"]["total_comments"], 14)
        self.assertEqual(report["summary"]["labeled_clusters"], 1)
        self.assertEqual(report["summary"]["total_change_cards"], 1)
        self.assertEqual(report["summary"]["change_type_counts"]["modified"], 1)
        self.assertEqual(report["summary"]["alignment_signal_counts"]["high"], 1)
        self.assertEqual(report["summary"]["comment_attribution_stats"]["attributed"], 2)
        self.assertEqual(report["summary"]["labeling"]["model"], "qwen3:14b")
        self.assertEqual(report["summary"]["labeling"]["total_input_tokens"], 111)
        self.assertEqual(report["change_cards"][0]["related_clusters"][0]["comment_count"], 2)
        self.assertEqual(
            report["change_cards"][0]["related_clusters"][0]["label"],
            "Small Refinery Compliance Timeline and Costs",
        )

        with open(csv_path, "r", encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))

        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]), 19)
        self.assertEqual(rows[0]["top_cluster_label"], "Small Refinery Compliance Timeline and Costs")
        self.assertEqual(rows[0]["related_cluster_count"], "1")

        with open(html_path, "r", encoding="utf-8") as handle:
            html = handle.read()

        self.assertIn("filter-change-type", html)
        self.assertIn("filter-signal", html)
        self.assertIn("Small Refinery Compliance Timeline and Costs", html)
        self.assertIn("No cards match the current filters.", html)

    def test_missing_change_cards_still_writes_partial_outputs(self):
        docket_id = "EPA-HQ-OAR-2020-0272"
        base_dir = os.path.join(self.corpus_dir, docket_id)
        os.makedirs(base_dir, exist_ok=True)

        self.write_json(
            os.path.join(base_dir, "comment_themes.json"),
            {
                "docket_id": docket_id,
                "total_comments": 2,
                "total_canonical_comments": 2,
                "total_clusters": 1,
                "clusters": [
                    {
                        "cluster_id": f"{docket_id}_cluster_0001",
                        "label": None,
                        "canonical_count": 2,
                        "total_raw_comments": 2,
                        "member_canonical_ids": ["c1", "c2"],
                        "top_keywords": ["deadline", "compliance"],
                        "commenter_type_distribution": {"individual": 2},
                    }
                ],
            },
        )

        result = generate_outputs.process_docket(docket_id, self.output_dir, force=True)

        self.assertIsNotNone(result)

        json_path = os.path.join(self.output_dir, docket_id, "report.json")
        csv_path = os.path.join(self.output_dir, docket_id, "report.csv")
        html_path = os.path.join(self.output_dir, docket_id, "report.html")

        with open(json_path, "r", encoding="utf-8") as handle:
            report = json.load(handle)

        self.assertEqual(report["schema_version"], "v1")
        self.assertEqual(report["change_cards"], [])
        self.assertEqual(report["summary"]["total_change_cards"], 0)
        self.assertIn("notes", report["summary"])
        self.assertNotIn("labeling", report["summary"])
        self.assertIn("change_cards.json not found", report["summary"]["notes"][0])

        with open(csv_path, "r", encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.reader(handle))

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0], generate_outputs.CSV_COLUMNS)

        with open(html_path, "r", encoding="utf-8") as handle:
            html = handle.read()

        self.assertIn("Change Cards (0 cards)", html)


if __name__ == "__main__":
    unittest.main()
