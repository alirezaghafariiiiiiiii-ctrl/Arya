import unittest
from arya_core.guard import REFUSAL, conversation_only

BT = chr(96) * 3
IMG = chr(33) + "[x](a.png)"

class ConversationOnlyTest(unittest.TestCase):
    def test_plain_chat_passes(self):
        text = "hello, how are you?"
        self.assertEqual(conversation_only(text), text)

    def test_code_block_refused(self):
        self.assertEqual(conversation_only(BT + "python print(1) " + BT), REFUSAL)

    def test_html_refused(self):
        self.assertEqual(conversation_only("<html><body>hi</body></html>"), REFUSAL)

    def test_image_refused(self):
        self.assertEqual(conversation_only(IMG), REFUSAL)

    def test_persian_plain_chat_passes(self):
        text = "\u0633\u0644\u0627\u0645\u060c \u0686\u0647 \u062e\u0628\u0631\u061f"
        self.assertEqual(conversation_only(text), text)

    def test_refusal_is_persian(self):
        self.assertTrue(any("\u0600" <= c <= "\u06ff" for c in REFUSAL))

    def test_persian_text_with_code_block_refused(self):
        text = "\u0627\u06cc\u0646 \u06a9\u062f \u0627\u0633\u062a: " + BT + "print(1)" + BT
        self.assertEqual(conversation_only(text), REFUSAL)

    def test_build_request_detected(self):
        from arya_core.guard import is_build_request
        self.assertTrue(is_build_request("یه بازی برام بساز"))
        self.assertTrue(is_build_request("کد بنویس"))
        self.assertTrue(is_build_request("write me a script"))
        self.assertFalse(is_build_request("امروز حالت چطوره؟"))


if __name__ == "__main__":
    unittest.main()
