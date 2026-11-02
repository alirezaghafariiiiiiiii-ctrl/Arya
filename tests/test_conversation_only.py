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

if __name__ == "__main__":
    unittest.main()
