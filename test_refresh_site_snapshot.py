import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO

import refresh_site_snapshot


class RefreshSiteSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)

        self.original_client = refresh_site_snapshot.label_clusters.OllamaClient
        self.original_label_process = refresh_site_snapshot.label_clusters.process_docket
        self.original_output_process = refresh_site_snapshot.generate_outputs.process_docket
        self.original_eval_process = refresh_site_snapshot.evaluate_pipeline.process_docket
        self.original_insight_process = refresh_site_snapshot.generate_insights.process_docket
        self.original_publish = refresh_site_snapshot.publish_site_snapshot.publish_snapshot
        self.original_preflight = refresh_site_snapshot.label_clusters.run_preflight
        self.addCleanup(self.restore_globals)

    def restore_globals(self):
        refresh_site_snapshot.label_clusters.OllamaClient = self.original_client
        refresh_site_snapshot.label_clusters.process_docket = self.original_label_process
        refresh_site_snapshot.generate_outputs.process_docket = self.original_output_process
        refresh_site_snapshot.evaluate_pipeline.process_docket = self.original_eval_process
        refresh_site_snapshot.generate_insights.process_docket = self.original_insight_process
        refresh_site_snapshot.publish_site_snapshot.publish_snapshot = self.original_publish
        refresh_site_snapshot.label_clusters.run_preflight = self.original_preflight

    def test_run_refresh_uses_no_think_for_qwen_and_publishes(self):
        calls = []

        class _FakeClient:
            def __init__(self, ollama_url):
                self.ollama_url = ollama_url

        refresh_site_snapshot.label_clusters.OllamaClient = _FakeClient
        refresh_site_snapshot.label_clusters.run_preflight = lambda *args, **kwargs: {
            "ollama_url": "http://localhost:11434",
            "model": "qwen3:14b",
            "profile": {
                "model": "qwen3:14b",
                "display_name": "Qwen 3 14B",
                "purpose": "Accuracy-first local labeling baseline",
                "recommended_no_think": True,
                "status": "supported",
                "warning": None,
                "supported": True,
            },
            "warnings": [],
        }
        refresh_site_snapshot.label_clusters.process_docket = lambda client, docket_id, model, force, no_think, **kwargs: (
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
        refresh_site_snapshot.generate_insights.process_docket = lambda docket_id, output_dir: (
            calls.append(("insights", docket_id, output_dir))
            or {"top_findings": [{"finding_id": "finding-001"}], "priority_cards": [{"card_id": "card-001"}]}
        )
        refresh_site_snapshot.publish_site_snapshot.publish_snapshot = (
            lambda docket_ids, output_dir, site_data_dir, release_metadata=None: (
                calls.append(("publish", tuple(docket_ids), output_dir, site_data_dir, release_metadata))
                or {"release_id": "20260405T010203Z"}
            )
        )

        result = refresh_site_snapshot.run_refresh(
            docket_ids=["EPA-HQ-OAR-2020-0430"],
            model="qwen3:14b",
            ollama_url="http://localhost:11434",
            force_labels=True,
            skip_evaluate=False,
            skip_insights=False,
            skip_publish=False,
            output_dir="OUT",
            gold_dir="GOLD",
            site_data_dir="SITE",
        )

        self.assertTrue(result["no_think"])
        self.assertEqual(calls[0], ("label", "EPA-HQ-OAR-2020-0430", "qwen3:14b", True, True, "http://localhost:11434"))
        self.assertEqual(calls[1], ("output", "EPA-HQ-OAR-2020-0430", "OUT", True))
        self.assertEqual(calls[2], ("eval", "EPA-HQ-OAR-2020-0430", "GOLD", "OUT"))
        self.assertEqual(calls[3], ("insights", "EPA-HQ-OAR-2020-0430", "OUT"))
        self.assertEqual(calls[4][0:4], ("publish", ("EPA-HQ-OAR-2020-0430",), "OUT", "SITE"))
        self.assertEqual(calls[4][4]["model"], "qwen3:14b")
        self.assertTrue(calls[4][4]["no_think"])
        self.assertEqual(calls[4][4]["insights"], {"available": 1, "not_available": 0})
        self.assertEqual(result["insight_summaries"]["EPA-HQ-OAR-2020-0430"], {"finding_count": 1, "priority_card_count": 1})

    def test_run_refresh_skips_eval_and_publish_when_requested(self):
        calls = []

        class _FakeClient:
            def __init__(self, ollama_url):
                self.ollama_url = ollama_url

        refresh_site_snapshot.label_clusters.OllamaClient = _FakeClient
        refresh_site_snapshot.label_clusters.run_preflight = lambda *args, **kwargs: {
            "ollama_url": "http://localhost:11434",
            "model": "gemma3:12b-it-q8_0",
            "profile": {
                "model": "gemma3:12b-it-q8_0",
                "display_name": "Gemma 3 12B Instruct Q8",
                "purpose": "Speed-first local labeling alternative",
                "recommended_no_think": False,
                "status": "supported",
                "warning": None,
                "supported": True,
            },
            "warnings": [],
        }
        refresh_site_snapshot.label_clusters.process_docket = lambda client, docket_id, model, force, no_think, **kwargs: (
            calls.append(("label", docket_id, no_think)) or {"docket_id": docket_id}
        )
        refresh_site_snapshot.generate_outputs.process_docket = lambda docket_id, output_dir, force: (
            calls.append(("output", docket_id)) or {"docket_id": docket_id}
        )
        refresh_site_snapshot.evaluate_pipeline.process_docket = lambda docket_id, gold_dir, output_dir: (
            calls.append(("eval", docket_id)) or {"docket_id": docket_id, "status": "available"}
        )
        refresh_site_snapshot.generate_insights.process_docket = lambda docket_id, output_dir: (
            calls.append(("insights", docket_id)) or {"top_findings": [], "priority_cards": []}
        )
        refresh_site_snapshot.publish_site_snapshot.publish_snapshot = lambda docket_ids, output_dir, site_data_dir, release_metadata=None: (
            calls.append(("publish", tuple(docket_ids), release_metadata)) or {"release_id": "unused"}
        )

        result = refresh_site_snapshot.run_refresh(
            docket_ids=["EPA-HQ-OAR-2020-0430"],
            model="gemma3:12b-it-q8_0",
            ollama_url="http://localhost:11434",
            force_labels=False,
            skip_evaluate=True,
            skip_insights=False,
            skip_publish=True,
            output_dir="OUT",
            gold_dir="GOLD",
            site_data_dir="SITE",
        )

        self.assertFalse(result["no_think"])
        self.assertEqual(
            calls,
            [
                ("label", "EPA-HQ-OAR-2020-0430", False),
                ("output", "EPA-HQ-OAR-2020-0430"),
                ("insights", "EPA-HQ-OAR-2020-0430"),
            ],
        )

        calls.clear()
        result = refresh_site_snapshot.run_refresh(
            docket_ids=["EPA-HQ-OAR-2020-0430"],
            model="gemma3:12b-it-q8_0",
            ollama_url="http://localhost:11434",
            force_labels=False,
            skip_evaluate=False,
            skip_insights=True,
            skip_publish=False,
            output_dir="OUT",
            gold_dir="GOLD",
            site_data_dir="SITE",
        )

        self.assertEqual(
            [call[0] for call in calls],
            ["label", "output", "eval", "publish"],
        )
        self.assertEqual(calls[3][1], ("EPA-HQ-OAR-2020-0430",))
        self.assertEqual(calls[3][2]["insights"], {"available": 0, "not_available": 0})
        self.assertEqual(result["insight_summaries"], {})

    def test_run_refresh_logs_distinct_insight_errors(self):
        calls = []

        class _FakeClient:
            def __init__(self, ollama_url):
                self.ollama_url = ollama_url

        refresh_site_snapshot.label_clusters.OllamaClient = _FakeClient
        refresh_site_snapshot.label_clusters.run_preflight = lambda *args, **kwargs: {
            "ollama_url": "http://localhost:11434",
            "model": "qwen3:14b",
            "profile": {
                "model": "qwen3:14b",
                "display_name": "Qwen 3 14B",
                "purpose": "Accuracy-first local labeling baseline",
                "recommended_no_think": True,
                "status": "supported",
                "warning": None,
                "supported": True,
            },
            "warnings": [],
        }
        refresh_site_snapshot.label_clusters.process_docket = lambda client, docket_id, model, force, no_think, **kwargs: (
            calls.append(("label", docket_id)) or {"docket_id": docket_id}
        )
        refresh_site_snapshot.generate_outputs.process_docket = lambda docket_id, output_dir, force: (
            calls.append(("output", docket_id)) or {"docket_id": docket_id}
        )
        refresh_site_snapshot.evaluate_pipeline.process_docket = lambda docket_id, gold_dir, output_dir: (
            calls.append(("eval", docket_id)) or {"docket_id": docket_id, "status": "available"}
        )

        def _raise_insight_error(docket_id, output_dir):
            calls.append(("insights", docket_id))
            raise RuntimeError("boom")

        refresh_site_snapshot.generate_insights.process_docket = _raise_insight_error
        refresh_site_snapshot.publish_site_snapshot.publish_snapshot = (
            lambda docket_ids, output_dir, site_data_dir, release_metadata=None: (
                calls.append(("publish", tuple(docket_ids), release_metadata)) or {"release_id": "20260405T010203Z"}
            )
        )

        stdout = StringIO()
        with redirect_stdout(stdout):
            result = refresh_site_snapshot.run_refresh(
                docket_ids=["EPA-HQ-OAR-2020-0430"],
                model="qwen3:14b",
                ollama_url="http://localhost:11434",
                force_labels=True,
                skip_evaluate=False,
                skip_insights=False,
                skip_publish=False,
                output_dir="OUT",
                gold_dir="GOLD",
                site_data_dir="SITE",
            )

        self.assertIn("[EPA-HQ-OAR-2020-0430] INSIGHT_ERROR: insight generation failed: boom", stdout.getvalue())
        self.assertIsNone(result["insight_summaries"]["EPA-HQ-OAR-2020-0430"])
        self.assertEqual(calls[4][2]["insights"], {"available": 0, "not_available": 1})


if __name__ == "__main__":
    unittest.main()
