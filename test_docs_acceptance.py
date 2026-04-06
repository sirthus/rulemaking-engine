import os
import unittest


ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
CHECK_PATHS = [
    "README.md",
    "BLUEPRINT.md",
    "CLAUDE.md",
    "label_clusters.py",
    "refresh_site_snapshot.py",
    "ollama_runtime.py",
]
BANNED_STRINGS = [
    "ANTHROPIC_API_KEY",
    "pip install anthropic",
    "Anthropic-compatible",
    "claude-haiku",
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
