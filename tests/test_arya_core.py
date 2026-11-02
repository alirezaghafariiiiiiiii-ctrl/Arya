import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from arya_core.engine import ConversationEngine, NO_MODEL_MESSAGE
from arya_core.memory import MemoryStore
from arya_core.persona import Persona
from arya_core.providers import EchoProvider, LocalProvider, Provider, ProviderError
from arya_core.sessions import SessionStore


class RecordingProvider(Provider):
    """Keep the most recent system prompt and messages for assertions."""

    def __init__(self):
        self.system = None
        self.messages = None

    def chat(self, system_prompt, messages):
        if system_prompt.startswith("این پیام را بررسی کن."):
            return "NO_FACT"
        self.system, self.messages = system_prompt, messages
        return "باشه"


class FactExtractionProvider(Provider):
    def __init__(self, extraction_result):
        self.extraction_result = extraction_result
        self.extraction_calls = 0

    def chat(self, system_prompt, messages):
        if system_prompt.startswith("این پیام را بررسی کن."):
            self.extraction_calls += 1
            return self.extraction_result
        return "پاسخ"


class FailingProvider(Provider):
    def chat(self, _system_prompt, _messages):
        raise ProviderError("قطع است")


class Base(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.memory = MemoryStore(self.path)

    def tearDown(self):
        self.memory.close()
        os.remove(self.path)


class TestMemory(Base):
    def test_add_search_delete_count(self):
        memory_id = self.memory.add("اسم من علی است")
        self.assertEqual(self.memory.count(), 1)
        found = self.memory.search("اسم من چیه؟")
        self.assertEqual([memory.id for memory in found], [memory_id])
        self.assertTrue(self.memory.delete(memory_id))
        self.assertFalse(self.memory.delete(memory_id))
        self.assertEqual(self.memory.count(), 0)

    def test_search_matches_persian_yeh_inflection(self):
        memory_id = self.memory.add("من عاشق غذای مادرم هستم")
        found = self.memory.search("من از چه غذایی خوشم میاد؟")
        self.assertEqual([memory.id for memory in found], [memory_id])

    def test_duplicate_not_saved_twice(self):
        first_id = self.memory.add("من قهوه دوست دارم")
        second_id = self.memory.add("من  قهوه دوست دارم ")
        self.assertEqual(first_id, second_id)
        self.assertEqual(self.memory.count(), 1)

    def test_arabic_letters_and_digits_normalized(self):
        self.memory.add("شماره‌ی من ۱۲۳۴ است")
        self.assertEqual(len(self.memory.search("1234")), 1)
        self.memory.add("كتاب يادداشت")
        self.assertEqual(len(self.memory.search("کتاب")), 1)

    def test_empty_and_stopword_only_queries(self):
        self.memory.add("اسم من علی است")
        self.assertEqual(self.memory.search("من چیه"), [])
        self.assertEqual(self.memory.search(""), [])
        with self.assertRaises(ValueError):
            self.memory.add("   ")

    def test_like_wildcards_are_not_treated_as_search_terms(self):
        self.memory.add("نمره ۱۰۰ درصد شد")
        self.assertEqual(self.memory.search("%"), [])

    def test_persists_across_connections(self):
        self.memory.add("شهر من تهران است")
        other = MemoryStore(self.path)
        try:
            self.assertEqual(other.count(), 1)
        finally:
            other.close()


class TestEngine(Base):
    def test_persona_yaml_is_formatted_as_a_prompt(self):
        persona = Persona(Path(__file__).parents[1] / "config" / "persona.yaml")

        prompt = persona.to_prompt()

        self.assertIn("تو «آریا» هستی", prompt)
        self.assertIn("لحن: صمیمی، مستقیم، کوتاه", prompt)
        self.assertIn(
            "پرهیز کن از: تعارف اضافه، پاسخ‌های طولانی بی‌دلیل، تکرار سؤال کاربر",
            prompt,
        )
        self.assertIn("ارزش‌ها: صداقت، اختصار، همدلی", prompt)
        self.assertIn("یادم می‌مونه", prompt)
        self.assertIn("نمی‌دانم", prompt)

    def test_default_personality_is_casual_honest_and_concise(self):
        provider = RecordingProvider()
        engine = ConversationEngine(provider, self.memory)

        engine.generate_response("سلام")

        self.assertIn("نامت آریا است", provider.system)
        self.assertIn("صمیمی، مستقیم و محترمانه", provider.system)
        self.assertIn("با همدلی موقعیت کاربر را درک کن", provider.system)
        self.assertIn("سؤالش را بی‌دلیل تکرار نکن", provider.system)
        self.assertIn("صریح بگو «نمی‌دانم»", provider.system)
        self.assertIn("با «شاید» ابهام نساز", provider.system)
        self.assertIn("همیشه کاربر را با «تو» خطاب کن", provider.system)
        self.assertIn("چطور می‌تونم کمکت کنم؟", provider.system)
        self.assertIn("فقط یک بار کوتاه مثل «یادم می‌مونه» تأییدش کن", provider.system)

    def test_persisted_session_resumes_and_reset_starts_a_new_one(self):
        sessions = SessionStore(self.path)
        try:
            engine = ConversationEngine(
                RecordingProvider(), self.memory, session_store=sessions
            )
            first_session_id = engine.session_id
            engine.generate_response("سلام")
            self.assertEqual(sessions.count_messages(first_session_id), 2)

            resumed = ConversationEngine(
                RecordingProvider(), self.memory, session_store=sessions
            )
            self.assertEqual(
                [message.content for message in resumed.get_history()],
                ["سلام", "باشه"],
            )
            self.assertEqual(resumed.session_id, first_session_id)

            resumed.generate_response("/reset")
            self.assertNotEqual(resumed.session_id, first_session_id)
            self.assertEqual(sessions.count_messages(first_session_id), 2)
            self.assertEqual(sessions.get_messages(resumed.session_id), [])
        finally:
            sessions.close()

    def test_explicit_session_id_loads_that_session(self):
        sessions = SessionStore(self.path)
        try:
            older_session = sessions.create_session("older")
            sessions.add_turn(older_session, "پیام قدیمی", "پاسخ قدیمی")
            latest_session = sessions.create_session("latest")
            sessions.add_turn(latest_session, "پیام جدید", "پاسخ جدید")

            engine = ConversationEngine(
                RecordingProvider(),
                self.memory,
                session_store=sessions,
                session_id=older_session,
            )

            self.assertEqual(engine.session_id, older_session)
            self.assertEqual(
                [message.content for message in engine.get_history()],
                ["پیام قدیمی", "پاسخ قدیمی"],
            )
            self.assertNotEqual(engine.session_id, latest_session)
        finally:
            sessions.close()

    def test_explicit_unknown_session_id_is_rejected(self):
        sessions = SessionStore(self.path)
        try:
            with self.assertRaisesRegex(ValueError, "Unknown session"):
                ConversationEngine(
                    RecordingProvider(),
                    self.memory,
                    session_store=sessions,
                    session_id="missing",
                )
        finally:
            sessions.close()

    def test_explicit_user_fact_is_saved_automatically(self):
        provider = FactExtractionProvider("FACT: من در تهران زندگی می‌کنم")
        engine = ConversationEngine(provider, self.memory)

        engine.generate_response("من در تهران زندگی می‌کنم")

        self.assertEqual(provider.extraction_calls, 1)
        self.assertEqual(
            [item.text for item in self.memory.list_all()],
            ["من در تهران زندگی می‌کنم"],
        )

    def test_uncertain_or_invalid_extraction_is_not_saved(self):
        provider = FactExtractionProvider("NO_FACT")
        engine = ConversationEngine(provider, self.memory)
        engine.generate_response("تهران خوبه؟")
        self.assertEqual(self.memory.count(), 0)

        for result in (
            "شاید کاربر در تهران زندگی می‌کند",
            "FACT: یاسر",
        ):
            with self.subTest(result=result):
                provider = FactExtractionProvider(result)
                engine = ConversationEngine(provider, self.memory)
                with self.assertLogs("arya_core.engine", level="WARNING"):
                    engine.generate_response("تهران خوبه؟")
                self.assertEqual(self.memory.count(), 0)

    def test_manual_remember_command_is_not_extracted_twice(self):
        provider = FactExtractionProvider("FACT: باید نادیده گرفته شود")
        engine = ConversationEngine(provider, self.memory)

        engine.generate_response("/remember من در تهران زندگی می‌کنم")

        self.assertEqual(provider.extraction_calls, 0)
        self.assertEqual(self.memory.count(), 1)

    def test_remember_reset_then_recall(self):
        provider = RecordingProvider()
        engine = ConversationEngine(provider, self.memory)
        self.assertIn(
            "ذخیره شد",
            engine.generate_response("/remember اسم من علی است"),
        )
        engine.reset()
        engine.generate_response("اسم من چیه؟")
        self.assertIn("اسم من علی است", provider.system)

    def test_unrelated_question_gets_no_memory_block(self):
        provider = RecordingProvider()
        engine = ConversationEngine(provider, self.memory)
        engine.generate_response("/remember اسم من علی است")
        engine.generate_response("هوا چطوره")
        self.assertIn("دانسته‌ی مرتبطی", provider.system)

    def test_memory_prompt_treats_memories_as_user_facts(self):
        provider = RecordingProvider()
        engine = ConversationEngine(provider, self.memory)
        engine.generate_response("/remember من عاشق غذای مادرم هستم")
        engine.generate_response("من از چه غذایی خوشم میاد؟")
        self.assertIn("از اطلاعات زیر برای پاسخ به کاربر استفاده کن", provider.system)
        self.assertIn("نه نقل‌قولی", provider.system)
        self.assertIn("معنای جمله‌ها و علاقه‌ها را استنباط کن", provider.system)
        self.assertIn("کاربر غذای مادرش را دوست دارد", provider.system)
        self.assertIn("از غذای مادرت خوشت می‌آید؛ نوع غذا مشخص نشده", provider.system)
        self.assertIn("درباره‌ی کاربر با «تو» حرف بزن", provider.system)
        self.assertIn("جزئیات ناموجود را نساز", provider.system)
        self.assertIn("من عاشق غذای مادرم هستم", provider.system)

    def test_memory_prompt_disambiguates_first_person_name(self):
        provider = RecordingProvider()
        engine = ConversationEngine(provider, self.memory)
        engine.generate_response("/remember اسم من رضاست")
        engine.generate_response("اسم من چیه؟")
        self.assertIn("ضمیر «من» در خاطره‌ها به کاربر اشاره دارد", provider.system)
        self.assertIn("پاسخ بده «اسمت رضاست.»", provider.system)
        self.assertIn("- اسم من رضاست", provider.system)

    def test_commands(self):
        engine = ConversationEngine(EchoProvider(), self.memory)
        engine.generate_response("/remember الف")
        engine.generate_response("/remember ب")
        self.assertEqual(engine.generate_response("/count"), "تعداد خاطرات: 2")
        listing = engine.generate_response("/memories")
        self.assertIn("1: الف", listing)
        self.assertEqual(engine.generate_response("/forget 1"), "حذف شد.")
        self.assertEqual(
            engine.generate_response("/forget 99"), "چنین خاطره‌ای پیدا نشد."
        )
        self.assertIn("شماره", engine.generate_response("/forget x"))
        self.assertIn("ناشناخته", engine.generate_response("/foo"))

    def test_commands_not_added_to_history(self):
        engine = ConversationEngine(EchoProvider(), self.memory)
        engine.generate_response("/remember الف")
        self.assertEqual(list(engine.history), [])
        engine.generate_response("سلام")
        self.assertEqual(len(engine.history), 2)

    def test_no_provider(self):
        engine = ConversationEngine(None, self.memory)
        self.assertEqual(engine.generate_response("سلام"), NO_MODEL_MESSAGE)
        self.assertIn("ذخیره شد", engine.generate_response("/remember الف"))

    def test_provider_error_preserves_user_message_in_session(self):
        sessions = SessionStore(self.path)
        try:
            engine = ConversationEngine(
                FailingProvider(), self.memory, session_store=sessions
            )
            reply = engine.generate_response("سلام")
            self.assertIn("خطا", reply)
            self.assertEqual(
                [message.content for message in engine.history],
                ["سلام"],
            )
            self.assertEqual(
                sessions.get_messages(engine.session_id),
                [{"role": "user", "content": "سلام"}],
            )
        finally:
            sessions.close()

    def test_history_is_trimmed(self):
        engine = ConversationEngine(EchoProvider(), self.memory, max_history=4)
        for index in range(10):
            engine.generate_response(f"پیام {index}")
        self.assertEqual(len(engine.history), 4)


class TestLocalProvider(unittest.TestCase):
    def test_missing_model_file_has_a_clear_error(self):
        with self.assertRaisesRegex(FileNotFoundError, "مدل پیدا نشد"):
            LocalProvider(Path("missing-model.gguf"))

    def test_chat_uses_local_model_and_formats_messages(self):
        class FakeLlama:
            def __init__(self, **kwargs):
                self.options = kwargs
                self.request = None

            def create_chat_completion(self, **kwargs):
                self.request = kwargs
                return {"choices": [{"message": {"content": " پاسخ محلی "}}]}

        fake_module = types.ModuleType("llama_cpp")
        fake_module.Llama = FakeLlama
        with tempfile.NamedTemporaryFile(suffix=".gguf") as model_file:
            with patch.dict(sys.modules, {"llama_cpp": fake_module}):
                provider = LocalProvider(Path(model_file.name), n_threads=2)

            self.assertEqual(
                provider.chat("system", [{"role": "user", "content": "سلام"}]),
                "پاسخ محلی",
            )
            self.assertEqual(
                provider.llm.request["messages"],
                [
                    {"role": "system", "content": "system"},
                    {"role": "user", "content": "سلام"},
                ],
            )
            self.assertEqual(provider.llm.options["n_threads"], 2)


class TestSessionStore(unittest.TestCase):
    def test_session_messages_persist_and_delete_cascades(self):
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            store = SessionStore(path)
            session_id = store.create_session("session1")
            store.add_turn(session_id, "سلام", "درود")
            store.close()

            store = SessionStore(path)
            self.assertEqual(
                store.get_messages(session_id),
                [
                    {"role": "user", "content": "سلام"},
                    {"role": "assistant", "content": "درود"},
                ],
            )
            self.assertEqual(store.list_sessions()[0]["msg_count"], 2)
            self.assertTrue(store.delete_session(session_id))
            self.assertEqual(store.count_messages(session_id), 0)
            store.close()
        finally:
            os.remove(path)


if __name__ == "__main__":
    unittest.main(verbosity=2)
