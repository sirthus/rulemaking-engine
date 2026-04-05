import unittest

import generate_change_cards


class ChangeCardsTests(unittest.TestCase):
    def test_build_preamble_links_prefers_cfr_citation_match(self):
        cards = [
            {
                "card_id": "card-1",
                "docket_id": "TEST",
                "_card_cfr_numbers": ["60.5"],
                "_heading_tokens": {"emissions", "limits"},
            }
        ]
        preamble_sections = [
            {
                "section_id": "preamble-1",
                "heading": "Response on § 60.5",
                "order": 0,
                "body_tokens": {"emissions", "limits"},
            }
        ]
        preamble_cfr_index = {"60.5": ["preamble-1"]}

        generate_change_cards.build_preamble_links(cards, preamble_sections, preamble_cfr_index)

        self.assertEqual(len(cards[0]["preamble_links"]), 1)
        self.assertEqual(cards[0]["preamble_links"][0]["link_type"], "cfr_citation")

    def test_build_preamble_links_uses_keyword_fallback(self):
        cards = [
            {
                "card_id": "card-1",
                "docket_id": "TEST",
                "_card_cfr_numbers": [],
                "_heading_tokens": {"ozone", "transport"},
            }
        ]
        preamble_sections = [
            {
                "section_id": "preamble-1",
                "heading": "Keyword overlap",
                "order": 0,
                "body_tokens": {"ozone", "transport", "policy"},
            }
        ]

        generate_change_cards.build_preamble_links(cards, preamble_sections, {})

        self.assertEqual(len(cards[0]["preamble_links"]), 1)
        self.assertEqual(cards[0]["preamble_links"][0]["link_type"], "keyword")

    def test_build_preamble_links_caps_at_five(self):
        cards = [
            {
                "card_id": "card-1",
                "docket_id": "TEST",
                "_card_cfr_numbers": [],
                "_heading_tokens": {"ozone", "transport"},
            }
        ]
        preamble_sections = [
            {
                "section_id": f"preamble-{index}",
                "heading": f"Heading {index}",
                "order": index,
                "body_tokens": {"ozone", "transport", f"token{index}"},
            }
            for index in range(8)
        ]

        generate_change_cards.build_preamble_links(cards, preamble_sections, {})

        self.assertEqual(len(cards[0]["preamble_links"]), 5)

    def test_build_preamble_links_does_not_double_count_cfr_and_keyword_match(self):
        cards = [
            {
                "card_id": "card-1",
                "docket_id": "TEST",
                "_card_cfr_numbers": ["60.5"],
                "_heading_tokens": {"ozone", "transport"},
            }
        ]
        preamble_sections = [
            {
                "section_id": "preamble-1",
                "heading": "Response on § 60.5",
                "order": 0,
                "body_tokens": {"ozone", "transport", "policy"},
            }
        ]
        preamble_cfr_index = {"60.5": ["preamble-1"]}

        generate_change_cards.build_preamble_links(cards, preamble_sections, preamble_cfr_index)

        self.assertEqual(len(cards[0]["preamble_links"]), 1)
        self.assertEqual(cards[0]["preamble_links"][0]["preamble_section_id"], "preamble-1")

    def test_added_card_skips_related_comments_but_keeps_preamble_links(self):
        card = {
            "change_type": "added",
            "proposed_section_id": None,
        }
        related_comments = generate_change_cards.build_related_comments(card, {"section-1": [{"comment_id": "c1"}]})
        self.assertEqual(related_comments, [])

        cards = [
            {
                "card_id": "card-added",
                "docket_id": "TEST",
                "_card_cfr_numbers": ["60.5"],
                "_heading_tokens": {"emissions", "limits"},
            }
        ]
        preamble_sections = [
            {
                "section_id": "preamble-1",
                "heading": "Response on § 60.5",
                "order": 0,
                "body_tokens": {"emissions", "limits"},
            }
        ]
        preamble_cfr_index = {"60.5": ["preamble-1"]}

        generate_change_cards.build_preamble_links(cards, preamble_sections, preamble_cfr_index)

        self.assertEqual(len(cards[0]["preamble_links"]), 1)


if __name__ == "__main__":
    unittest.main()
