import os
from pathlib import Path
from llama_cpp import Llama

class ProviderError(Exception):
    pass

class EchoProvider:
    def chat(self, system_prompt, messages, stream=False):
        yield "(echo) " + (messages[-1]['content'] if messages else '')

class LocalProvider:
    def __init__(self, model_path: Path, n_ctx=2048, n_threads=4):
        self.llm = Llama(
            model_path=str(model_path),
            n_ctx=n_ctx,
            n_threads=n_threads,
            n_batch=512,
            n_gpu_layers=0,
            use_mmap=True,
            verbose=False,
        )

    def chat(self, system_prompt, messages, stream=False):
        if stream:
            return self.chat_stream(system_prompt, messages)
        formatted = [{"role": "system", "content": system_prompt}]
        formatted.extend(messages)
        out = self.llm.create_chat_completion(
            messages=formatted, temperature=0.6, top_p=0.9,
            max_tokens=150, repeat_penalty=1.25, stream=False,
        )
        return out["choices"][0]["message"]["content"].strip()

    def chat_stream(self, system_prompt, messages):
        formatted = [{"role": "system", "content": system_prompt}]
        formatted.extend(messages)
        out = self.llm.create_chat_completion(
            messages=formatted, temperature=0.6, top_p=0.9,
            max_tokens=150, repeat_penalty=1.25, stream=True,
        )
        for chunk in out:
            delta = chunk["choices"][0].get("delta", {})
            piece = delta.get("content", "")
            if piece:
                yield piece

Provider = LocalProvider
