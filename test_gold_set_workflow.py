import json
import os
import tempfile
import unittest

import gold_set_workflow


class GoldSetWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.site_data_dir = os.path.join(self.temp_dir.name, "site_data")
        self.corpus_dir = os.path.join(self.temp_dir.name, "corpus")
        self.docket_id = "EPA-HQ-OAR-2020-0430"

    def write_json(self, path: str, payload):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)

    def test_validate_gold_set_payload_accepts_blind_human_payload(self):
        errors = gold_set_workflow.validate_gold_set_payload(
            {
                "docket_id": self.docket_id,
                "annotator": "reviewer-a",
                "annotation_method": "blind_human",
                "blinded": True,
                "alignments": [
                    {
                        "proposed_section_id": "p1",
                        "final_section_id": "f1",
                        "expected_match_type": "exact_heading",
                        "expected_change_type": "modified",
                    }
                ],
                "cluster_relevance": [
                    {
                        "card_id": "card-1",
                        "cluster_id": "cluster-1",
                        "relevance": "relevant",
                    }
                ],
            },
            expected_docket_id=self.docket_id,
        )

        self.assertEqual(errors, [])

    def test_validate_gold_set_payload_rejects_invalid_relevance(self):
        errors = gold_set_workflow.validate_gold_set_payload(
            {
                "docket_id": self.docket_id,
                "alignments": [],
                "cluster_relevance": [
                    {
                        "card_id": "card-1",
                        "cluster_id": "cluster-1",
                        "relevance": "maybe",
                    }
                ],
            }
        )

        self.assertTrue(errors)
        self.assertIn("invalid relevance", errors[0])

    def test_build_blinded_annotation_packet_uses_snapshot_and_hides_gold_fields(self):
        self.write_json(
            os.path.join(self.site_data_dir, "current", "manifest.json"),
            {
                "schema_version": "v1",
                "release_id": "20260406T120000Z",
                "published_at": "2026-04-06T12:00:00+00:00",
            },
        )
        self.write_json(
            os.path.join(self.site_data_dir, "current", "dockets", self.docket_id, "report.json"),
            {
                "schema_version": "v1",
                "docket_id": self.docket_id,
                "clusters": [
                    {
                        "cluster_id": "cluster-1",
                        "label": "Example cluster",
                        "label_description": "Example description.",
                        "canonical_count": 2,
                        "total_raw_comments": 3,
                        "top_keywords": ["ozone", "cost"],
                        "commenter_type_distribution": {"individual": 2},
                    }
                ],
                "change_cards": [
                    {
                        "card_id": "card-1",
                        "change_type": "modified",
                        "proposed_section_id": "p1",
                        "final_section_id": "f1",
                        "proposed_heading": "Proposed heading",
                        "final_heading": "Final heading",
                        "proposed_text_snippet": "Proposed text",
                        "final_text_snippet": "Final text",
                        "related_clusters": [{"cluster_id": "cluster-1"}],
                    }
                ],
            },
        )
        self.write_json(
            os.path.join(self.corpus_dir, self.docket_id, "section_alignment.json"),
            [
                {
                    "proposed_section_id": "p1",
                    "final_section_id": "f1",
                    "proposed_heading": "Proposed heading",
                    "final_heading": "Final heading",
                }
            ],
        )
        self.write_json(
            os.path.join(self.corpus_dir, self.docket_id, "proposed_rule.json"),
            [{"section_id": "p1", "heading": "Proposed heading", "body_text": "Proposed body"}],
        )
        self.write_json(
            os.path.join(self.corpus_dir, self.docket_id, "final_rule.json"),
            [{"section_id": "f1", "heading": "Final heading", "body_text": "Final body"}],
        )

        packet = gold_set_workflow.build_blinded_annotation_packet(
            self.docket_id,
            site_data_dir=self.site_data_dir,
            corpus_dir=self.corpus_dir,
        )
        template = gold_set_workflow.build_gold_set_template(packet)

        self.assertEqual(packet["packet_type"], "blind_annotation_packet")
        self.assertEqual(packet["source_snapshot_release_id"], "20260406T120000Z")
        self.assertNotIn("expected_change_type", packet["alignment_tasks"][0])
        self.assertEqual(template["annotation_method"], "blind_human")
        self.assertTrue(template["blinded"])
        self.assertEqual(template["cluster_relevance"][0]["card_id"], "card-1")


if __name__ == "__main__":
    unittest.main()
