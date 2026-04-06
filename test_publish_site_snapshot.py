import json
import os
import tempfile
import unittest

import publish_site_snapshot


class PublishSiteSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.output_dir = os.path.join(self.temp_dir.name, "outputs")
        self.site_data_dir = os.path.join(self.temp_dir.name, "site_data")

    def write_json(self, path: str, payload):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)

    def test_publish_snapshot_writes_release_and_current_views(self):
        docket_id = "EPA-HQ-OAR-2020-0430"
        docket_output_dir = os.path.join(self.output_dir, docket_id)
        self.write_json(
            os.path.join(docket_output_dir, "report.json"),
            {
                "schema_version": "v1",
                "docket_id": docket_id,
                "generated_at": "2026-04-05T00:00:00+00:00",
                "summary": {
                    "total_clusters": 12,
                    "labeled_clusters": 12,
                    "total_change_cards": 146,
                },
            },
        )
        self.write_json(
            os.path.join(docket_output_dir, "eval_report.json"),
            {
                "schema_version": "v1",
                "docket_id": docket_id,
                "evaluated_at": "2026-04-05T01:00:00+00:00",
                "status": "available",
            },
        )
        self.write_json(os.path.join(docket_output_dir, "report.csv"), {"ignored": True})
        self.write_json(os.path.join(docket_output_dir, "report.html"), {"ignored": True})

        manifest = publish_site_snapshot.publish_snapshot(
            [docket_id],
            self.output_dir,
            self.site_data_dir,
            release_id="20260405T010203Z",
        )

        release_dir = os.path.join(self.site_data_dir, "releases", "20260405T010203Z")
        current_dir = os.path.join(self.site_data_dir, "current")
        release_manifest_path = os.path.join(release_dir, "manifest.json")
        current_index_path = os.path.join(current_dir, "dockets", "index.json")
        current_report_path = os.path.join(current_dir, "dockets", docket_id, "report.json")
        current_eval_path = os.path.join(current_dir, "dockets", docket_id, "eval_report.json")

        self.assertEqual(manifest["schema_version"], "v1")
        self.assertTrue(os.path.exists(release_manifest_path))
        self.assertTrue(os.path.exists(current_index_path))
        self.assertTrue(os.path.exists(current_report_path))
        self.assertTrue(os.path.exists(current_eval_path))
        self.assertFalse(os.path.exists(os.path.join(current_dir, "dockets", docket_id, "report.csv")))
        self.assertFalse(os.path.exists(os.path.join(current_dir, "dockets", docket_id, "report.html")))

        with open(current_index_path, "r", encoding="utf-8") as handle:
            docket_index = json.load(handle)

        self.assertEqual(docket_index["schema_version"], "v1")
        self.assertEqual(docket_index["dockets"][0]["docket_id"], docket_id)
        self.assertEqual(docket_index["dockets"][0]["report_path"], f"dockets/{docket_id}/report.json")

    def test_publish_snapshot_requires_eval_report(self):
        docket_id = "EPA-HQ-OAR-2020-0430"
        docket_output_dir = os.path.join(self.output_dir, docket_id)
        self.write_json(
            os.path.join(docket_output_dir, "report.json"),
            {"schema_version": "v1", "docket_id": docket_id},
        )

        with self.assertRaisesRegex(RuntimeError, "Missing required evaluation artifact"):
            publish_site_snapshot.publish_snapshot([docket_id], self.output_dir, self.site_data_dir)


if __name__ == "__main__":
    unittest.main()
