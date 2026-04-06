import unittest

import cluster_comments


class ClusterCommentsTests(unittest.TestCase):
    def test_tfidf_keywords_ranks_rare_terms_above_common_terms(self):
        scores, keyword_lists = cluster_comments.tfidf_keywords(
            {
                "doc1": ["apple", "zephyr"],
                "doc2": ["apple", "banana"],
                "doc3": ["apple", "citrus"],
            }
        )

        self.assertGreater(scores["doc1"]["zephyr"], scores["doc1"]["apple"])
        self.assertEqual(keyword_lists["doc1"][0], "zephyr")

    def test_tfidf_keywords_caps_output_at_fifteen(self):
        tokens = [f"token{i}" for i in range(20)]
        _scores, keyword_lists = cluster_comments.tfidf_keywords({"doc1": tokens})

        self.assertLessEqual(len(keyword_lists["doc1"]), 15)

    def test_tfidf_keywords_handles_empty_corpus(self):
        scores, keyword_lists = cluster_comments.tfidf_keywords({})

        self.assertEqual(scores, {})
        self.assertEqual(keyword_lists, {})

    def test_tfidf_keywords_handles_single_document(self):
        scores, keyword_lists = cluster_comments.tfidf_keywords({"doc1": ["zephyr", "zephyr", "apple"]})

        self.assertIn("doc1", scores)
        self.assertIn("zephyr", scores["doc1"])
        self.assertIn("apple", keyword_lists["doc1"])

    def test_tokenize_excludes_stopwords_before_tfidf(self):
        tokens = cluster_comments.tokenize("This rule comment discusses zephyr impacts.")
        _scores, keyword_lists = cluster_comments.tfidf_keywords({"doc1": tokens})

        self.assertNotIn("rule", keyword_lists["doc1"])
        self.assertNotIn("comment", keyword_lists["doc1"])
        self.assertIn("zephyr", keyword_lists["doc1"])


if __name__ == "__main__":
    unittest.main()
