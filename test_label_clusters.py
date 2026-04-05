import json
import os
import tempfile
import unittest

import label_clusters


class _FakeTextBlock:
    def __init__(self, text: str):
        self.text = text


class _FakeUsage:
    def __init__(self, input_tokens: int = 10, output_tokens: int = 5):
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens


class _FakeResponse:
    def __init__(self, text: str):
        self.content = [_FakeTextBlock(text)]
        self.usage = _FakeUsage()


class _FakeMessages:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.responses.pop(0)


class _FakeClient:
    def __init__(self, responses):
        self.messages = _FakeMessages(responses)


class LabelClustersTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.original_corpus_dir = label_clusters.CORPUS_DIR
        self.addCleanup(self.restore_globals)
        label_clusters.CORPUS_DIR = os.path.join(self.temp_dir.name, "corpus")

    def restore_globals(self):
        label_clusters.CORPUS_DIR = self.original_corpus_dir

    def write_json(self, path: str, payload):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)

    def test_process_docket_force_failure_clears_existing_label_fields(self):
        docket_id = "EPA-HQ-OAR-2020-0272"
        base_dir = os.path.join(label_clusters.CORPUS_DIR, docket_id)
        themes_path = os.path.join(base_dir, "comment_themes.json")
        comments_path = os.path.join(base_dir, "comments.json")

        self.write_json(
            themes_path,
            {
                "clusters": [
                    {
                        "cluster_id": "cluster-1",
                        "member_canonical_ids": ["c1"],
                        "label": "Old label",
                        "label_description": "Old description",
                    }
                ]
            },
        )
        self.write_json(comments_path, [{"comment_id": "c1", "text": "Example comment"}])

        original_label_cluster = label_clusters.label_cluster
        self.addCleanup(lambda: setattr(label_clusters, "label_cluster", original_label_cluster))
        label_clusters.label_cluster = lambda *args, **kwargs: (None, None, {"error": "request_failed"})

        summary = label_clusters.process_docket(object(), docket_id, "test-model", force=True)

        self.assertIsNotNone(summary)
        with open(themes_path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)

        cluster = payload["clusters"][0]
        self.assertIsNone(cluster["label"])
        self.assertIsNone(cluster["label_description"])

    def test_label_cluster_retries_with_no_think_suffix(self):
        client = _FakeClient(
            [
                _FakeResponse("not json"),
                _FakeResponse('{"label":"Test label","description":"Short description."}'),
            ]
        )
        cluster = {"cluster_id": "cluster-1", "member_canonical_ids": ["c1"]}
        comments_by_id = {"c1": {"text": "Example text"}}

        label, description, _meta = label_clusters.label_cluster(
            client,
            "EPA-HQ-OAR-2020-0272",
            cluster,
            comments_by_id,
            "test-model",
            no_think=True,
        )

        self.assertEqual(label, "Test label")
        self.assertEqual(description, "Short description.")
        self.assertEqual(len(client.messages.calls), 2)
        self.assertTrue(client.messages.calls[0]["messages"][0]["content"].endswith("\n\n/no_think"))
        self.assertTrue(client.messages.calls[1]["messages"][0]["content"].endswith("\n\n/no_think"))


if __name__ == "__main__":
    unittest.main()
