"""Language-model providers for ARIA."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path


class ProviderError(RuntimeError):
    """Raised when a language-model provider request fails."""


class Provider:
    def chat(self, system_prompt: str, messages: list[dict[str, str]]) -> str:
        """Return a model response for the supplied prompt and chat history."""
        raise NotImplementedError


class EchoProvider(Provider):
    """Test provider that echoes the most recent user message."""

    def chat(self, system_prompt: str, messages: list[dict[str, str]]) -> str:
        if system_prompt.startswith("این پیام را بررسی کن."):
            return "NO_FACT"
        last_message = messages[-1]["content"] if messages else ""
        return f"(echo) {last_message}"


class OllamaProvider(Provider):
    """Connect to a local Ollama chat API without extra dependencies."""

    def __init__(
        self,
        model: str = "llama3.2",
        host: str = "http://localhost:11434",
        timeout: float = 120.0,
    ):
        self.model = model
        self.host = host.rstrip("/")
        self.timeout = timeout

    def chat(self, system_prompt: str, messages: list[dict[str, str]]) -> str:
        payload = {
            "model": self.model,
            "stream": False,
            "messages": [
                {"role": "system", "content": system_prompt},
                *messages,
            ],
        }
        request = urllib.request.Request(
            f"{self.host}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, OSError) as error:
            raise ProviderError(f"به Ollama وصل نشدم ({error})") from error
        except (KeyError, TypeError, ValueError) as error:
            raise ProviderError(f"پاسخ نامعتبر از Ollama ({error})") from error

        try:
            content = data["message"]["content"]
        except (KeyError, TypeError) as error:
            raise ProviderError(f"پاسخ نامعتبر از Ollama ({error})") from error
        if not isinstance(content, str):
            raise ProviderError("پاسخ نامعتبر از Ollama (متن پاسخ رشته نیست)")
        return content.strip()


class LocalProvider(Provider):
    """Run a GGUF model locally through llama.cpp without network access."""

    def __init__(
        self,
        model_path: Path,
        n_ctx: int = 4096,
        n_threads: int | None = None,
    ):
        model_path = Path(model_path)
        if not model_path.is_file():
            raise FileNotFoundError(
                f"مدل پیدا نشد: {model_path}\n"
                f"یک فایل GGUF در {model_path.parent} قرار بده."
            )

        try:
            from llama_cpp import Llama
        except ImportError as error:
            raise ProviderError(
                "برای استفاده از مدل محلی، بستهٔ llama-cpp-python را نصب کن."
            ) from error

        self.llm = Llama(
            model_path=str(model_path),
            n_ctx=n_ctx,
            n_threads=n_threads,
            verbose=False,
        )

    def chat(self, system_prompt: str, messages: list[dict[str, str]]) -> str:
        output = self.llm.create_chat_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                *messages,
            ],
            temperature=0.3,
            top_p=0.9,
            max_tokens=512,
        )
        try:
            content = output["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as error:
            raise ProviderError("پاسخ نامعتبر از مدل محلی") from error
        if not isinstance(content, str):
            raise ProviderError("پاسخ نامعتبر از مدل محلی (متن پاسخ رشته نیست)")
        return content.strip()



# --- پاسخ جریانی (streaming): تکه‌تکه و هم‌زمان با تولید ---
def _local_chat_stream(self, system_prompt, messages):
    llm = getattr(self, "llm", None) or getattr(self, "_llm", None)
    formatted = [{"role": "system", "content": system_prompt}]
    formatted.extend(messages)
    stream = llm.create_chat_completion(
        messages=formatted,
        temperature=0.3,
        top_p=0.9,
        top_k=40,
        max_tokens=150,
        repeat_penalty=1.15,
        stream=True,
    )
    for chunk in stream:
        delta = chunk["choices"][0].get("delta", {})
        piece = delta.get("content")
        if piece:
            yield piece


LocalProvider.chat_stream = _local_chat_stream


_orig_local_init = LocalProvider.__init__


def _init_with_warmup(self, *args, **kwargs):
    _orig_local_init(self, *args, **kwargs)
    try:
        self.llm.create_chat_completion(messages=[{"role": "user", "content": "سلام"}], max_tokens=1)
    except Exception:
        pass


LocalProvider.__init__ = _init_with_warmup


import os as _os
import time as _time

if _os.getenv("ARIA_DEBUG"):
    _orig_cs = LocalProvider.chat_stream

    def _dbg_cs(self, system_prompt, messages):
        text = system_prompt + " ".join(m["content"] for m in messages)
        n = len(self.llm.tokenize(text.encode("utf-8")))
        t = _time.time()
        first = True
        count = 0
        for piece in _orig_cs(self, system_prompt, messages):
            if first:
                print("\n[DEBUG] prompt ~%d tokens, first piece after %.1fs" % (n, _time.time() - t))
                first = False
            count += 1
            yield piece
        print("\n[DEBUG] %d pieces, total %.1fs" % (count, _time.time() - t))

    LocalProvider.chat_stream = _dbg_cs


_prev_init = LocalProvider.__init__


def _init_cached(self, *args, **kwargs):
    _prev_init(self, *args, **kwargs)
    try:
        from llama_cpp import LlamaRAMCache
        self.llm.set_cache(LlamaRAMCache(capacity_bytes=512 * 1024 * 1024))
    except Exception:
        pass


LocalProvider.__init__ = _init_cached
