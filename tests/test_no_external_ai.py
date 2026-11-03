import pathlib
import re
import unittest
from unittest import mock

from arya_core import web

ROOT = pathlib.Path(__file__).resolve().parent.parent
FORBIDDEN = [
    r"\b(import|from)\s+(openai|anthropic|cohere|mistralai|groq|google\.generativeai)\b",
    r"api[_-]?key",
    r"Bearer\s",
]


class NoExternalAiTest(unittest.TestCase):
    def test_ai_hosts_are_detected(self):
        for host in ("api.openai.com", "chat.openai.com", "claude.ai", "www.perplexity.ai",
                     "gemini.google.com", "api.anthropic.com", "openrouter.ai"):
            self.assertTrue(web._is_ai_host(host), host)

    def test_normal_hosts_are_allowed(self):
        for host in ("fa.wikipedia.org", "html.duckduckgo.com", "example.com", "max.ai"):
            self.assertFalse(web._is_ai_host(host), host)

    def test_fetch_to_ai_host_is_blocked_before_any_request(self):
        with mock.patch.object(web.requests, "get", side_effect=AssertionError("network used")):
            self.assertIsNone(web._get("https://api.openai.com/v1/chat/completions"))

    def test_code_has_no_ai_api_usage(self):
        files = list((ROOT / "arya_core").rglob("*.py")) + [ROOT / "app.py", ROOT / "main.py"]
        for path in files:
            if not path.exists():
                continue
            text = path.read_text(encoding="utf-8")
            for pattern in FORBIDDEN:
                self.assertIsNone(re.search(pattern, text, re.I), f"{path.name}: {pattern}")


if __name__ == "__main__":
    unittest.main()
