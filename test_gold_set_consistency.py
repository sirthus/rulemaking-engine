import os
import unittest

import align_corpus
import gold_set_workflow


class GoldSetConsistencyTests(unittest.TestCase):
    def test_top_level_gold_sets_match_corpus_consistency_rules(self):
        gold_files = sorted(
            file_name
            for file_name in os.listdir(gold_set_workflow.GOLD_DIR)
            if file_name.endswith(".json")
            and os.path.isfile(os.path.join(gold_set_workflow.GOLD_DIR, file_name))
        )

        self.assertTrue(gold_files, "expected at least one top-level gold-set JSON file")

        for file_name in gold_files:
            gold_path = os.path.join(gold_set_workflow.GOLD_DIR, file_name)
            gold = gold_set_workflow.read_json(gold_path)
            docket_id = gold["docket_id"]
            proposed_sections = self._sections_by_id(docket_id, "proposed_rule.json")
            final_sections = self._sections_by_id(docket_id, "final_rule.json")

            with self.subTest(gold_file=file_name):
                for index, entry in enumerate(gold.get("alignments", []), start=1):
                    proposed_id = entry.get("proposed_section_id")
                    final_id = entry.get("final_section_id")

                    if proposed_id is not None:
                        self.assertIn(proposed_id, proposed_sections, f"alignment {index} references unknown proposed section")
                    if final_id is not None:
                        self.assertIn(final_id, final_sections, f"alignment {index} references unknown final section")

                    if entry.get("expected_change_type") == "removed":
                        self.assertIsNone(final_id, f"alignment {index} removed entries must not keep a final_section_id")

                    if proposed_id is None or final_id is None:
                        continue

                    proposed_section = proposed_sections[proposed_id]
                    final_section = final_sections[final_id]

                    if entry.get("expected_match_type") == "exact_heading":
                        self.assertEqual(
                            proposed_section.get("heading"),
                            final_section.get("heading"),
                            f"alignment {index} exact_heading entry has different headings",
                        )

                    if entry.get("expected_change_type") == "unchanged":
                        self.assertFalse(
                            align_corpus.body_text_changed(proposed_section, final_section),
                            f"alignment {index} unchanged entry has body text changes",
                        )

    def _sections_by_id(self, docket_id: str, file_name: str) -> dict[str, dict]:
        path = os.path.join(gold_set_workflow.CORPUS_DIR, docket_id, file_name)
        return {
            section["section_id"]: section
            for section in gold_set_workflow.read_json(path)
            if section.get("section_id")
        }


if __name__ == "__main__":
    unittest.main()
