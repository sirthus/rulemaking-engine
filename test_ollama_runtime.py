import unittest

import requests

import ollama_runtime


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
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    def get(self, url, timeout=None):
        self.calls.append({"url": url, "timeout": timeout})
        if self.error is not None:
            raise self.error
        return self.response


class OllamaRuntimeTests(unittest.TestCase):
    def test_resolve_supported_profile(self):
        profile = ollama_runtime.resolve_model_profile("qwen3:14b")
        self.assertTrue(profile["supported"])
        self.assertTrue(profile["recommended_no_think"])

    def test_resolve_unknown_profile_is_experimental(self):
        profile = ollama_runtime.resolve_model_profile("custom-model")
        self.assertFalse(profile["supported"])
        self.assertEqual(profile["status"], "experimental")

    def test_run_preflight_success(self):
        session = _FakeSession(
            response=_FakeResponse(
                payload={"models": [{"model": "qwen3:14b"}, {"name": "gemma3:12b-it-q8_0"}]}
            )
        )

        result = ollama_runtime.run_preflight(
            "http://localhost:11434/",
            "qwen3:14b",
            session=session,
            timeout_seconds=12,
        )

        self.assertEqual(result["ollama_url"], "http://localhost:11434")
        self.assertEqual(result["profile"]["display_name"], "Qwen 3 14B")
        self.assertEqual(session.calls[0]["url"], "http://localhost:11434/api/tags")
        self.assertEqual(session.calls[0]["timeout"], 12)

    def test_run_preflight_missing_model(self):
        session = _FakeSession(response=_FakeResponse(payload={"models": [{"model": "gemma3:12b-it-q8_0"}]}))

        with self.assertRaisesRegex(RuntimeError, "ollama pull qwen3:14b"):
            ollama_runtime.run_preflight("http://localhost:11434", "qwen3:14b", session=session)

    def test_run_preflight_connection_error(self):
        session = _FakeSession(error=requests.exceptions.ConnectionError("boom"))

        with self.assertRaisesRegex(RuntimeError, "Could not reach Ollama"):
            ollama_runtime.run_preflight("http://localhost:11434", "qwen3:14b", session=session)

    def test_run_preflight_timeout(self):
        session = _FakeSession(error=requests.exceptions.Timeout("boom"))

        with self.assertRaisesRegex(RuntimeError, "timed out"):
            ollama_runtime.run_preflight("http://localhost:11434", "qwen3:14b", session=session)

    def test_run_preflight_malformed_json(self):
        session = _FakeSession(response=_FakeResponse(payload=ValueError("bad json")))

        with self.assertRaisesRegex(RuntimeError, "malformed JSON"):
            ollama_runtime.run_preflight("http://localhost:11434", "qwen3:14b", session=session)


if __name__ == "__main__":
    unittest.main()
