import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout

import pipeline_utils


class PipelineUtilsTests(unittest.TestCase):
    def test_normalize_whitespace(self):
        self.assertEqual(pipeline_utils.normalize_whitespace("  alpha\n\n beta\tgamma  "), "alpha beta gamma")

    def test_normalize_text_preserves_plain_text_behavior(self):
        self.assertEqual(pipeline_utils.normalize_text("  Caf\u00e9   "), "café")

    def test_normalize_text_can_strip_html(self):
        self.assertEqual(
            pipeline_utils.normalize_text("Hello &amp; <b>World</b>", strip_html=True),
            "hello & world",
        )

    def test_normalize_heading_can_strip_outline_prefix(self):
        self.assertEqual(
            pipeline_utils.normalize_heading("A. Supplemental Ozone Requirements", strip_outline_prefix=True),
            "supplemental ozone requirements",
        )
        self.assertEqual(
            pipeline_utils.normalize_heading("§ 52.38 Revised Requirements", strip_outline_prefix=True),
            "52 38 revised requirements",
        )

    def test_atomic_write_helpers_and_read_json(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            payload_path = os.path.join(temp_dir, "nested", "payload.json")
            text_path = os.path.join(temp_dir, "nested", "notes.txt")
            bytes_path = os.path.join(temp_dir, "nested", "blob.bin")

            pipeline_utils.atomic_write_json(payload_path, {"status": "ok"}, trailing_newline=True)
            pipeline_utils.atomic_write_text(text_path, "hello")
            pipeline_utils.atomic_write_bytes(bytes_path, b"bytes")

            with open(payload_path, "r", encoding="utf-8") as handle:
                raw_payload = handle.read()
            self.assertTrue(raw_payload.endswith("\n"))
            self.assertEqual(json.loads(raw_payload), {"status": "ok"})
            self.assertEqual(pipeline_utils.read_json(payload_path), {"status": "ok"})

            with open(text_path, "r", encoding="utf-8") as handle:
                self.assertEqual(handle.read(), "hello")
            with open(bytes_path, "rb") as handle:
                self.assertEqual(handle.read(), b"bytes")

    def test_print_line_supports_docket_and_message_variants(self):
        stream = io.StringIO()
        with redirect_stdout(stream):
            pipeline_utils.print_line("TEST", "EPA-HQ-OAR-2020-0430", "done")
            pipeline_utils.print_line("TEST", "done without docket")

        self.assertEqual(
            stream.getvalue().splitlines(),
            [
                "[TEST]  EPA-HQ-OAR-2020-0430  done",
                "[TEST]  done without docket",
            ],
        )


if __name__ == "__main__":
    unittest.main()
