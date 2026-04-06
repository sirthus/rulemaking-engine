import tempfile
import unittest

import refresh_site_snapshot


class RefreshSiteSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)

        self.original_client = refresh_site_snapshot.label_clusters.OllamaClient
        self.original_label_process = refresh_site_snapshot.label_clusters.process_docket
        self.original_output_process = refresh_site_snapshot.generate_outputs.process_docket
        self.original_eval_process = refresh_site_snapshot.evaluate_pipeline.process_docket
        self.original_publish = refresh_site_snapshot.publish_site_snapshot.publish_snapshot
        self.addCleanup(self.restore_globals)

    def restore_globals(self):
        refresh_site_snapshot.label_clusters.OllamaClient = self.original_client
        refresh_site_snapshot.label_clusters.process_docket = self.original_label_process
        refresh_site_snapshot.generate_outputs.process_docket = self.original_output_process
        refresh_site_snapshot.evaluate_pipeline.process_docket = self.original_eval_process
        refresh_site_snapshot.publish_site_snapshot.publish_snapshot = self.original_publish

    def test_run_refresh_uses_no_think_for_qwen_and_publishes(self):
        calls = []

        class _FakeClient:
            def __init__(self, ollama_url):
                self.ollama_url = ollama_url

        refresh_site_snapshot.label_clusters.OllamaClient = _FakeClient
        refresh_site_snapshot.label_clusters.process_docket = lambda client, docket_id, model, force, no_think: (
            calls.append(("label", docket_id, model, force, no_think, client.ollama_url))
            or {"docket_id": docket_id}
        )
        refresh_site_snapshot.generate_outputs.process_docket = lambda docket_id, output_dir, force: (
            calls.append(("output", docket_id, output_dir, force)) or {"docket_id": docket_id}
        )
        refresh_site_snapshot.evaluate_pipeline.process_docket = lambda docket_id, gold_dir, output_dir: (
            calls.append(("eval", docket_id, gold_dir, output_dir))
            or {"docket_id": docket_id, "status": "available"}
        )
        refresh_site_snapshot.publish_site_snapshot.publish_snapshot = (
            lambda docket_ids, output_dir, site_data_dir: (
                calls.append(("publish", tuple(docket_ids), output_dir, site_data_dir))
                or {"release_id": "20260405T010203Z"}
            )
        )

        result = refresh_site_snapshot.run_refresh(
            docket_ids=["EPA-HQ-OAR-2020-0430"],
            model="qwen3:14b",
            ollama_url="http://localhost:11434",
            force_labels=True,
            skip_evaluate=False,
            skip_publish=False,
            output_dir="OUT",
            gold_dir="GOLD",
            site_data_dir="SITE",
        )

        self.assertTrue(result["no_think"])
        self.assertEqual(calls[0], ("label", "EPA-HQ-OAR-2020-0430", "qwen3:14b", True, True, "http://localhost:11434"))
        self.assertEqual(calls[1], ("output", "EPA-HQ-OAR-2020-0430", "OUT", True))
        self.assertEqual(calls[2], ("eval", "EPA-HQ-OAR-2020-0430", "GOLD", "OUT"))
        self.assertEqual(calls[3], ("publish", ("EPA-HQ-OAR-2020-0430",), "OUT", "SITE"))

    def test_run_refresh_skips_eval_and_publish_when_requested(self):
        calls = []

        class _FakeClient:
            def __init__(self, ollama_url):
                self.ollama_url = ollama_url

        refresh_site_snapshot.label_clusters.OllamaClient = _FakeClient
        refresh_site_snapshot.label_clusters.process_docket = lambda client, docket_id, model, force, no_think: (
            calls.append(("label", docket_id, no_think)) or {"docket_id": docket_id}
        )
        refresh_site_snapshot.generate_outputs.process_docket = lambda docket_id, output_dir, force: (
            calls.append(("output", docket_id)) or {"docket_id": docket_id}
        )
        refresh_site_snapshot.evaluate_pipeline.process_docket = lambda docket_id, gold_dir, output_dir: (
            calls.append(("eval", docket_id)) or {"docket_id": docket_id}
        )
        refresh_site_snapshot.publish_site_snapshot.publish_snapshot = lambda docket_ids, output_dir, site_data_dir: (
            calls.append(("publish", tuple(docket_ids))) or {"release_id": "unused"}
        )

        result = refresh_site_snapshot.run_refresh(
            docket_ids=["EPA-HQ-OAR-2020-0430"],
            model="gemma3:12b-it-q8_0",
            ollama_url="http://localhost:11434",
            force_labels=False,
            skip_evaluate=True,
            skip_publish=True,
            output_dir="OUT",
            gold_dir="GOLD",
            site_data_dir="SITE",
        )

        self.assertFalse(result["no_think"])
        self.assertEqual(calls, [("label", "EPA-HQ-OAR-2020-0430", False), ("output", "EPA-HQ-OAR-2020-0430")])


if __name__ == "__main__":
    unittest.main()
