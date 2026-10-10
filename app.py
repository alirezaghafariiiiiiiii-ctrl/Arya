import os
import requests
import gradio as gr

OWNER_USER = os.environ.get("ARYA_OWNER_USER", "")
OWNER_PASSWORD = os.environ.get("ARYA_OWNER_PASSWORD", "")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
MODEL = os.environ.get("OPENROUTER_MODEL", "openai/gpt-4o-mini")

SYSTEM_PROMPT = """
تو آریا هستی؛ دستیار شخصی و فارسی‌زبان مالک.
با احترام، صمیمی و روشن پاسخ بده.
اطلاعات محرمانه را افشا نکن.
"""


def chat(message, history):
    if not OPENROUTER_API_KEY:
        return "کلید OpenRouter در تنظیمات Render تنظیم نشده است."

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for item in history or []:
        if isinstance(item, dict) and item.get("role") in ("user", "assistant"):
            content = item.get("content")
            if isinstance(content, str):
                messages.append({"role": item["role"], "content": content})
    messages.append({"role": "user", "content": message})

    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
            },
            json={"model": MODEL, "messages": messages},
            timeout=60,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"OpenRouter error: {e}")
        return "ارتباط با سرویس هوش مصنوعی برقرار نشد. تنظیمات را بررسی کن."


configured = bool(OWNER_USER and OWNER_PASSWORD)

if configured:
    demo = gr.ChatInterface(
        fn=chat,
        type="messages",
        title="آریا | دستیار شخصی",
        description="ورود خصوصی مالک",
    )
else:
    demo = gr.Interface(
        fn=lambda m: "ابتدا ARYA_OWNER_USER و ARYA_OWNER_PASSWORD را در Render تنظیم کن.",
        inputs=gr.Textbox(label="پیام"),
        outputs=gr.Textbox(label="وضعیت"),
        title="Arya — Setup Required",
    )

demo.queue()
demo.launch(
    server_name="0.0.0.0",
    server_port=int(os.environ.get("PORT", 10000)),
    auth=(OWNER_USER, OWNER_PASSWORD) if configured else None,
)
