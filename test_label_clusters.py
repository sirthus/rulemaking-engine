import json
import os
import tempfile
import unittest

import requests

import label_clusters


class _FakeResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


class _FakeSession:
    def __init__(self, responses=None, error=None):
        self.responses = list(responses or [])
        self.error = error
        self.calls = []

    def post(self, url, json=None, timeout=None):
        self.calls.append({"url": url, "json": json, "timeout": timeout})
        if self.error is not None:
            raise self.error
        return self.responses.pop(0)


class _FakeClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
        self.ollama_url = "http://localhost:11434"

    def chat(self, model, system_prompt, user_message):
        self.calls.append(
            {
                "model": model,
                "system_prompt": system_prompt,
                "user_message": user_message,
            }
        )
        return self.responses.pop(0)


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

    def test_ollama_client_chat_success(self):
        session = _FakeSession(
            responses=[
                _FakeResponse(
                    payload={
                        "message": {"role": "assistant", "content": '{"label":"A","description":"B"}'},
                        "prompt_eval_count": 12,
                        "eval_count": 8,
                    }
                )
            ]
        )
        client = label_clusters.OllamaClient("http://localhost:11434/", session=session, timeout_seconds=45)

        payload = client.chat("qwen3:14b", "system", "user")

        self.assertEqual(payload["prompt_eval_count"], 12)
        self.assertEqual(len(session.calls), 1)
        self.assertEqual(session.calls[0]["url"], "http://localhost:11434/api/chat")
        self.assertEqual(session.calls[0]["timeout"], 45)
        self.assertEqual(session.calls[0]["json"]["options"]["num_predict"], label_clusters.DEFAULT_NUM_PREDICT)

    def test_ollama_client_model_not_found(self):
        session = _FakeSession(
            responses=[
                _FakeResponse(status_code=404, payload={"error": "model 'missing' not found"})
            ]
        )
        client = label_clusters.OllamaClient(session=session)

        with self.assertRaisesRegex(RuntimeError, "ollama pull"):
            client.chat("missing", "system", "user")

    def test_ollama_client_connection_error(self):
        session = _FakeSession(error=requests.exceptions.ConnectionError("boom"))
        client = label_clusters.OllamaClient(session=session)

        with self.assertRaisesRegex(RuntimeError, "Could not reach Ollama"):
            client.chat("qwen3:14b", "system", "user")

    def test_ollama_client_timeout_error(self):
        session = _FakeSession(error=requests.exceptions.Timeout("boom"))
        client = label_clusters.OllamaClient(session=session)

        with self.assertRaisesRegex(RuntimeError, "timed out"):
            client.chat("qwen3:14b", "system", "user")

    def test_extract_response_text_ignores_thinking_field(self):
        raw_text = label_clusters.extract_response_text(
            {
                "message": {
                    "role": "assistant",
                    "thinking": "hidden reasoning",
                    "content": '{"label":"Visible","description":"Shown."}',
                }
            }
        )

        self.assertEqual(raw_text, '{"label":"Visible","description":"Shown."}')

    def test_label_cluster_retries_with_no_think_and_parses_fenced_json(self):
        client = _FakeClient(
            [
                {
                    "message": {"role": "assistant", "content": "not json"},
                    "prompt_eval_count": 10,
                    "eval_count": 4,
                    "total_duration": 2_000_000,
                    "load_duration": 1_000_000,
                    "prompt_eval_duration": 500_000,
                    "eval_duration": 500_000,
                },
                {
                    "message": {
                        "role": "assistant",
                        "content": '```json\n{"label":"Test label","description":"Short description."}\n```',
                    },
                    "prompt_eval_count": 12,
                    "eval_count": 6,
                    "total_duration": 3_000_000,
                    "load_duration": 1_000_000,
                    "prompt_eval_duration": 1_000_000,
                    "eval_duration": 1_000_000,
                },
            ]
        )
        cluster = {"cluster_id": "cluster-1", "member_canonical_ids": ["c1"]}
        comments_by_id = {"c1": {"text": "Example text"}}

        label, description, meta = label_clusters.label_cluster(
            client,
            "EPA-HQ-OAR-2020-0272",
            cluster,
            comments_by_id,
            "qwen3:14b",
            no_think=True,
        )

        self.assertEqual(label, "Test label")
        self.assertEqual(description, "Short description.")
        self.assertEqual(meta["input_tokens"], 22)
        self.assertEqual(meta["output_tokens"], 10)
        self.assertEqual(len(client.calls), 2)
        self.assertTrue(client.calls[0]["user_message"].endswith("\n\n/no_think"))
        self.assertTrue(client.calls[1]["user_message"].endswith("\n\n/no_think"))

    def test_label_cluster_reports_malformed_response(self):
        client = _FakeClient(
            [
                {
                    "message": {"role": "assistant"},
                    "prompt_eval_count": 3,
                    "eval_count": 2,
                }
            ]
        )
        cluster = {"cluster_id": "cluster-1", "member_canonical_ids": ["c1"]}

        label, description, meta = label_clusters.label_cluster(
            client,
            "EPA-HQ-OAR-2020-0272",
            cluster,
            {"c1": {"text": "Example text"}},
            "qwen3:14b",
        )

        self.assertIsNone(label)
        self.assertIsNone(description)
        self.assertEqual(meta["error"], "malformed_response")
        self.assertEqual(meta["input_tokens"], 3)
        self.assertEqual(meta["output_tokens"], 2)

    def test_process_docket_force_failure_clears_existing_label_fields_and_writes_label_run(self):
        docket_id = "EPA-HQ-OAR-2020-0272"
        base_dir = os.path.join(label_clusters.CORPUS_DIR, docket_id)
        themes_path = os.path.join(base_dir, "comment_themes.json")
        comments_path = os.path.join(base_dir, "comments.json")
        label_run_path = os.path.join(base_dir, "label_run.json")

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
        label_clusters.label_cluster = lambda *args, **kwargs: (
            None,
            None,
            {
                "runtime": "ollama",
                "prompt_version": label_clusters.PROMPT_VERSION,
                "model": "test-model",
                "input_tokens": 7,
                "output_tokens": 3,
                "total_duration_ms": 9.0,
                "load_duration_ms": 2.0,
                "prompt_eval_duration_ms": 3.0,
                "eval_duration_ms": 4.0,
                "request_count": 1,
                "no_think": False,
                "error": "request_failed",
            },
        )

        client = _FakeClient([])
        summary = label_clusters.process_docket(client, docket_id, "test-model", force=True)

        self.assertIsNotNone(summary)
        with open(themes_path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        with open(label_run_path, "r", encoding="utf-8") as handle:
            label_run = json.load(handle)

        cluster = payload["clusters"][0]
        self.assertIsNone(cluster["label"])
        self.assertIsNone(cluster["label_description"])
        self.assertEqual(label_run["schema_version"], "v1")
        self.assertEqual(label_run["failed"], 1)
        self.assertEqual(label_run["clusters"][0]["status"], "failed")
        self.assertEqual(label_run["clusters"][0]["input_tokens"], 7)


if __name__ == "__main__":
    unittest.main()
