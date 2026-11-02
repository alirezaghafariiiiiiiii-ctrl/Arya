import os
import sys
from arya_core.config import DB_PATH, MODEL_PATH
from arya_core.memory import MemoryStore
from arya_core.engine import ConversationEngine
from arya_core.providers import LocalProvider, EchoProvider

def build_provider():
    name = os.getenv("ARIA_PROVIDER", "").lower()
    if name == "local" or (name == "" and MODEL_PATH.exists()):
        print(f"✨ استفاده از مدل محلی: {MODEL_PATH.name}")
        return LocalProvider(model_path=MODEL_PATH)
    print("⚠️ مدل پیدا نشد. استفاده از EchoProvider")
    return EchoProvider()

def main():
    provider = build_provider()
    memory = MemoryStore(DB_PATH)
    
    # اینجا مدل به موتور پاس داده می‌شود
    engine = ConversationEngine(provider=provider, memory=memory)
    
    print("\nARIA Core v2 [آماده]. برای خروج Ctrl+C بزنید.")
    
    while True:
        try:
            text = input("\nتو: ").strip()
            if not text:
                continue
            
            if text == "/help":
                print("دستورات: /help, /reset, /count")
                continue
            elif text == "/reset":
                engine.reset()
                print("تاریخچه پاک شد.")
                continue
            elif text == "/count":
                print(f"تعداد خاطرات: {memory.count()}")
                continue
            
            response = engine.generate_response(text)
            print(f"ARIA: {response}")
            
        except KeyboardInterrupt:
            print("\nخداحافظ!")
            break
        except Exception as e:
            print(f"خطا: {e}")

if __name__ == "__main__":
    main()
