import gradio as gr
import os
from arya_core.config import DB_PATH, MODEL_PATH
from arya_core.memory import MemoryStore
from arya_core.engine import ConversationEngine
from arya_core.providers import LocalProvider

# لود کردن مدل و حافظه فقط یک بار در ابتدای اجرا
print("در حال بیدار کردن آریا...")
provider = LocalProvider(model_path=MODEL_PATH)
memory = MemoryStore(DB_PATH)
engine = ConversationEngine(provider=provider, memory=memory)

def chat_response(message, history):
    # ارسال پیام کاربر به موتور اصلی آریا
    try:
        response = engine.generate_response(message)
        return response
    except Exception as e:
        return f"خطا در سیستم: {e}"

def reset_chat():
    engine.reset()
    return None, "تاریخچه مکالمه پاک شد."

# طراحی رابط کاربری
with gr.Blocks(title="Arya AI", theme=gr.themes.Soft()) as demo:
    gr.Markdown("# 🌿 آریا (ARIA)")
    gr.Markdown("دستیار هوشمند مستقل و فارسی‌زبان شما")
    
    chatbot = gr.Chatbot(height=500, type="messages")
    
    with gr.Row():
        msg = gr.Textbox(
            show_label=False,
            placeholder="پیام خود را بنویسید...",
            container=False,
            scale=4
        )
        submit_btn = gr.Button("ارسال", scale=1, variant="primary")
        
    with gr.Row():
        reset_btn = gr.Button("پاک کردن تاریخچه (/reset)")
        
    def respond(message, chat_history):
        if not message.strip():
            return "", chat_history
        bot_message = chat_response(message, chat_history)
        chat_history.append({"role": "user", "content": message})
        chat_history.append({"role": "assistant", "content": bot_message})
        return "", chat_history

    # اتصال دکمه‌ها به توابع
    msg.submit(respond, [msg, chatbot], [msg, chatbot])
    submit_btn.click(respond, [msg, chatbot], [msg, chatbot])
    reset_btn.click(reset_chat, None, [chatbot, msg])

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)
