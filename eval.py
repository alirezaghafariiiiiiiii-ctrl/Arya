import time
from arya_core.config import DB_PATH, MODEL_PATH
from arya_core.memory import MemoryStore
from arya_core.engine import ConversationEngine
from arya_core.providers import LocalProvider

MESSAGES = [
    ("greeting", "سلام، خوبی؟"),
    ("store_fact", "من اهل شیرازم و عاشق قورمه‌سبزی هستم."),
    ("recall_city", "من اهل کجا بودم؟"),
    ("smalltalk", "چه خبر؟"),
    ("recall_food", "غذای مورد علاقه‌ام چیه؟"),
    ("guard_code", "یه تابع پایتون بنویس که اعداد رو جمع بزنه."),
    ("guard_image", "یک عکس گربه بساز."),
    ("web_link", "این لینک رو بخون: https://example.com"),
    ("smalltalk_2", "نظرت درباره هوش مصنوعی چیه؟"),
    ("memory_reflect", "خلاصه‌ی چیزهایی که از من می‌دونی رو بگو."),
]

def main():
    print(f"ARIA Eval — {MODEL_PATH.name}")
    provider = LocalProvider(model_path=MODEL_PATH)
    memory = MemoryStore(DB_PATH)
    engine = ConversationEngine(provider=provider, memory=memory)

    results = []
    print("-" * 60)
    
    for i, (label, text) in enumerate(MESSAGES, 1):
        print(f"\n[{i}/10] ({label}): {text}")
        t0 = time.perf_counter()
        first = None
        resp = ""
        
        try:
            for chunk in engine.generate_response(text, stream=True):
                if first is None:
                    first = time.perf_counter() - t0
                resp += str(chunk) 
        except Exception as e:
            resp = f"[ERROR: {type(e).__name__}: {e}]"

        total = time.perf_counter() - t0
        print(f"ARIA: {resp}")
        
        if first is not None:
            print(f"TIME: first={first:.2f}s, total={total:.2f}s")
        else:
            print(f"TIME: first=N/A, total={total:.2f}s")
            
        results.append((label, first, total, len(resp)))

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"{'label':16} | {'first':>7} | {'total':>7} | chars")
    print("-" * 60)
    
    for label, first, total, chars in results:
        f = f"{first:.2f}s" if first else "N/A"
        print(f"{label:16} | {f:>7} | {total:>6.2f}s | {chars}")
        
    print("=" * 60)

if __name__ == "__main__":
    main()
