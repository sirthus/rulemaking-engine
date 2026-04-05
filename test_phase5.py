import unittest

import dedup_comments
import generate_change_cards


class Phase5Tests(unittest.TestCase):
    def test_empty_text_comments_stay_unique(self):
        payload = dedup_comments.build_family_payload(
            "TEST-DOCKET",
            [
                {"comment_id": "c1", "text": "", "posted_date": "2024-01-01"},
                {"comment_id": "c2", "text": "   ", "posted_date": "2024-01-02"},
            ],
        )

        self.assertEqual(payload["unique_families"], 2)
        self.assertEqual(payload["unique_comment_families"], 2)
        self.assertEqual(payload["exact_duplicate_families"], 0)
        self.assertTrue(all(family["family_type"] == "unique" for family in payload["families"]))

    def test_dedup_detects_exact_and_near_duplicate_families(self):
        payload = dedup_comments.build_family_payload(
            "TEST-DOCKET",
            [
                {"comment_id": "c1", "text": "Please protect clean air in our state.", "posted_date": "2024-01-02"},
                {"comment_id": "c2", "text": "Please protect clean air in our state.", "posted_date": "2024-01-03"},
                {"comment_id": "c3", "text": "Please protect clean air in our state now.", "posted_date": "2024-01-01"},
                {"comment_id": "c4", "text": "A different submission entirely.", "posted_date": "2024-01-04"},
            ],
        )

        family_sizes = sorted(family["member_count"] for family in payload["families"])
        family_types = {family["family_type"] for family in payload["families"]}

        self.assertEqual(sum(family["member_count"] for family in payload["families"]), 4)
        self.assertIn(3, family_sizes)
        self.assertIn("form_letter", family_types)
        self.assertIn("unique", family_types)

    def test_build_alignment_signal_uses_family_dedup(self):
        card = {
            "related_comments": [
                {"comment_id": "c1", "attribution_method": "keyword", "confidence": "medium"},
                {"comment_id": "c2", "attribution_method": "keyword", "confidence": "medium"},
                {"comment_id": "c3", "attribution_method": "keyword", "confidence": "low"},
            ],
            "preamble_links": [],
        }
        dedup_metadata = {
            "dedup_available": True,
            "comment_to_family_id": {
                "c1": "fam1",
                "c2": "fam1",
                "c3": "fam2",
            },
            "family_member_count": {
                "fam1": 2,
                "fam2": 1,
            },
            "family_canonical": {},
        }

        signal = generate_change_cards.build_alignment_signal(card, dedup_metadata)

        self.assertEqual(signal["score"], 3)
        self.assertEqual(signal["level"], "medium")
        self.assertEqual(signal["features"]["comment_count"], 3)
        self.assertEqual(signal["features"]["unique_comment_count"], 2)
        self.assertEqual(signal["features"]["largest_family_size"], 2)
        self.assertIn("3 comments (2 unique arguments)", signal["evidence_note"])

    def test_build_alignment_signal_handles_null_comment_ids_independently(self):
        card = {
            "related_comments": [
                {"comment_id": None, "attribution_method": "keyword", "confidence": "medium"},
                {"comment_id": None, "attribution_method": "keyword", "confidence": "medium"},
            ],
            "preamble_links": [],
        }
        dedup_metadata = {
            "dedup_available": True,
            "comment_to_family_id": {},
            "family_member_count": {},
            "family_canonical": {},
        }

        signal = generate_change_cards.build_alignment_signal(card, dedup_metadata)

        self.assertEqual(signal["score"], 4)
        self.assertEqual(signal["features"]["unique_comment_count"], 2)
        self.assertEqual(signal["features"]["largest_family_size"], 1)


if __name__ == "__main__":
    unittest.main()
