import json
import os

import gradio as gr
import requests

APP_NAME = "Arya"  # هدرهای HTTP باید ASCII باشند؛ نام فارسی باعث UnicodeEncodeError می‌شد
API_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = os.getenv("OPENROUTER_MODEL", "openrouter/free").strip() or "openrouter/free"
SITE_URL = os.getenv("SITE_URL", "").strip()


def _int_env(name, default, lo, hi):
    try:
        return max(lo, min(hi, int(os.getenv(name, default))))
    except (TypeError, ValueError):
        return default


MAX_TOKENS = _int_env("MAX_TOKENS", 1500, 100, 8000)
HISTORY_LIMIT = _int_env("HISTORY_LIMIT", 16, 0, 60)
MAX_INPUT_CHARS = _int_env("MAX_INPUT_CHARS", 4000, 100, 20000)
TEMPERATURE = 0.7

DEFAULT_PERSONALITY = """تو آریا هستی؛ یک دستیار فارسی‌زبان با شخصیت دوستانه، باهوش، صبور و کاربردی.
- به‌طور پیش‌فرض فارسی روان بنویس، مگر کاربر زبان دیگری بخواهد.
- جواب‌ها را روشن و مرحله‌به‌مرحله بده.
- اگر چیزی را نمی‌دانی، صادقانه بگو و اطلاعات نساز.
- برای سؤال‌های ساده کوتاه و برای کارهای پیچیده مفصل پاسخ بده.
- با احترام و بدون قضاوت با کاربر صحبت کن.
"""

SYSTEM_PROMPT = os.getenv("AI_PERSONALITY", "").strip() or DEFAULT_PERSONALITY.strip()

ERROR_MESSAGES = {
    400: "درخواست نامعتبر بود. اگر مدل را دستی تنظیم کرده‌ای، نام آن را بررسی کن.",
    401: "کلید API اشتباه یا نامعتبر است (۴۰۱). OPENROUTER_API_KEY را بررسی کن.",
    402: "اعتبار حساب OpenRouter کافی نیست یا مدل پولی است (۴۰۲).",
    403: "دسترسی به این مدل یا درخواست مجاز نیست (۴۰۳).",
    404: "مدل پیدا نشد (۴۰۴). مقدار OPENROUTER_MODEL را بررسی کن.",
    408: "زمان پاسخ مدل تمام شد (۴۰۸). دوباره امتحان کن.",
    429: "تعداد درخواست‌ها زیاد است (۴۲۹). کمی صبر کن و دوباره بفرست.",
    500: "سرویس مدل خطای داخلی داد (۵۰۰). کمی بعد دوباره امتحان کن.",
    502: "مدل فعلاً در دسترس نیست (۵۰۲). دوباره امتحان کن.",
    503: "مدل فعلاً در دسترس نیست (۵۰۳). دوباره امتحان کن.",
}


def _text_of(content):
    """محتوای پیام را (رشته یا لیست بلوک‌ها) به متن ساده تبدیل می‌کند."""
    if isinstance(content, str):
        return content
    if isinstance(content, dict):
        return content.get("text", "") if isinstance(content.get("text"), str) else ""
    if isinstance(content, (list, tuple)):
        return "".join(_text_of(part) for part in content)
    return ""


def build_messages(message, history):
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    recent = list(history or [])[-HISTORY_LIMIT:] if HISTORY_LIMIT else []
    for item in recent:
        if isinstance(item, dict) and item.get("role") in ("user", "assistant"):
            text = _text_of(item.get("content")).strip()
            if text:
                messages.append({"role": item["role"], "content": text})
    messages.append({"role": "user", "content": message})
    return messages


def _error_text(resp):
    msg = ERROR_MESSAGES.get(resp.status_code)
    if msg:
        return msg
    try:
        detail = resp.json().get("error", {}).get("message", "")
    except ValueError:
        detail = ""
    extra = f" ({detail[:120]})" if detail else ""
    return f"خطای اتصال مدل ({resp.status_code}){extra}."


def respond(message, history):
    key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not key:
        yield "هنوز کلید اتصال مدل تنظیم نشده است. در پنل میزبانی، متغیر OPENROUTER_API_KEY را اضافه کن."
        return

    message = _text_of(message).strip()
    if not message:
        yield "پیام خالی است؛ چیزی بنویس."
        return
    if len(message) > MAX_INPUT_CHARS:
        yield f"پیام خیلی طولانی است (بیشینه {MAX_INPUT_CHARS} نویسه). لطفاً کوتاه‌ترش کن."
        return

    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "X-Title": APP_NAME,
    }
    if SITE_URL:
        headers["HTTP-Referer"] = SITE_URL

    payload = {
        "model": MODEL,
        "messages": build_messages(message, history),
        "temperature": TEMPERATURE,
        "max_tokens": MAX_TOKENS,
        "stream": True,
    }

    answer = ""
    try:
        with requests.post(
            API_URL, headers=headers, json=payload, stream=True, timeout=(10, 60)
        ) as r:
            if not r.ok:
                yield _error_text(r)
                return
            r.encoding = "utf-8"
            for raw in r.iter_lines(decode_unicode=True):
                if not raw or raw.startswith(":"):  # keep-alive / comment
                    continue
                if not raw.startswith("data:"):
                    continue
                data = raw[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                except ValueError:
                    continue
                if chunk.get("error"):
                    err = chunk["error"].get("message", "") if isinstance(chunk["error"], dict) else ""
                    if not answer:
                        yield f"مدل خطا برگرداند. {err[:150]}".strip()
                        return
                    break
                choices = chunk.get("choices") or []
                if not choices:
                    continue
                piece = (choices[0].get("delta") or {}).get("content")
                if isinstance(piece, str) and piece:
                    answer += piece
                    yield answer
    except requests.Timeout:
        if answer:
            yield answer + "\n\n⚠️ پاسخ ناقص ماند (زمان تمام شد)."
        else:
            yield "پاسخ‌گویی بیش از حد طول کشید. لطفاً دوباره امتحان کن."
        return
    except requests.RequestException:
        if answer:
            yield answer + "\n\n⚠️ ارتباط در میانهٔ پاسخ قطع شد."
        else:
            yield "اتصال ناموفق بود. اینترنت و وضعیت سرویس را بررسی کن."
        return

    if not answer.strip():
        yield "مدل پاسخ متنی برنگرداند؛ دوباره امتحان کن."


CSS = """
.gradio-container { max-width: 900px !important; margin: auto; }
.message, .message p, textarea { direction: rtl; text-align: right; }
.message pre, .message code { direction: ltr; text-align: left; }
footer { display: none !important; }
"""

with gr.Blocks(theme=gr.themes.Soft(), css=CSS, title="آریا | دستیار هوشمند") as demo:
    gr.Markdown(
        "# 🤖 آریا\n"
        "### دستیار هوشمند فارسی با شخصیت اختصاصی\n"
        "پیامت را بنویس؛ آریا پاسخ می‌دهد."
    )
    gr.ChatInterface(
        fn=respond,
        type="messages",
        chatbot=gr.Chatbot(type="messages", height=480, rtl=True),
        textbox=gr.Textbox(placeholder="اینجا بنویس…", container=False, rtl=True),
        examples=[
            "سلام آریا، خودت را معرفی کن.",
            "برای یادگیری پایتون یک برنامه ۷ روزه بده.",
            "برای ساخت یک بازی موبایلی از کجا شروع کنم؟",
        ],
        cache_examples=False,
    )

demo.queue(default_concurrency_limit=4, max_size=32)

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=int(os.getenv("PORT", "7860")))
