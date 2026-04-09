import os
import unittest


ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
CHECK_PATHS = [
    "README.md",
    "CLAUDE.md",
    "PROJECT_STATUS.md",
    "label_clusters.py",
    "generate_outputs.py",
    "evaluate_pipeline.py",
    "refresh_site_snapshot.py",
]
BANNED_STRINGS = [
    "ANTHROPIC_API_KEY",
    "pip install anthropic",
    "Anthropic-compatible",
    "claude-haiku",
    "PHASE8_SPEC.md",
    "PHASE9_SPEC.md",
    "PHASE9.1_SPEC.md",
    "PHASE10_SPEC.md",
    "test_phase5",
    "test_phase8",
    "Phase 8 outputs complete",
    "Phase 9 evaluation complete",
    "validated Phase 10 profile list",
]


class DocsAcceptanceTests(unittest.TestCase):
    def test_local_only_docs_and_runtime_language(self):
        for relative_path in CHECK_PATHS:
            path = os.path.join(ROOT_DIR, relative_path)
            with open(path, "r", encoding="utf-8") as handle:
                contents = handle.read()
            for banned in BANNED_STRINGS:
                self.assertNotIn(banned, contents, msg=f"{relative_path} still contains `{banned}`")


if __name__ == "__main__":
    unittest.main()
