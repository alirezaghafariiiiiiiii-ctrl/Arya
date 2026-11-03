import os
from pathlib import Path
from llama_cpp import Llama

class EchoProvider:
    def chat(self, system_prompt, messages, stream=False):
        last = messages[-1]["content"] if messages else ""
        yield f"(echo) {last}"

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
        formatted = [{"role": "system", "content": system_prompt}]
        formatted.extend(messages)
        
        out = self.llm.create_chat_completion(
            messages=formatted,
            temperature=0.6,       # دمای متعادل برای خلاقیت
            top_p=0.9,
            top_k=40,
            repeat_penalty=1.25,   # 👈 این عدد بالا رفت تا از تکرار "شام شام شام" جلوگیری کند
            max_tokens=150,
            stream=stream,
        )
        
        if stream:
            for chunk in out:
                delta = chunk["choices"][0].get("delta", {})
                if "content" in delta:
                    yield delta["content"]
        else:
            yield out["choices"][0]["message"]["content"].strip()

    def chat_stream(self, system_prompt, messages):
        """پشتیبانی از جریان‌سازی برای فایل streaming.py"""
        return self.chat(system_prompt, messages, stream=True)

# Alias for backwards compatibility
Provider = LocalProvider
