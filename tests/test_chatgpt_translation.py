import unittest

from scripts.chatgpt_translation import make_chunks, make_instructions, split_ending


class ChunkingTests(unittest.TestCase):
    def test_make_chunks_preserves_all_source_characters(self):
        samples = [
            "第一段\n\n第二段\n第三段\n",
            "这是一个很长的句子，没有标点，应该在合适的长度处分块。"
            "后面的内容也必须完整保留！还有一段？",
            "A\r\nB\r\n\r\nC",
            "只有一行，没有换行符",
        ]
        for sample in samples:
            with self.subTest(sample=sample):
                chunks = make_chunks(sample, maximum=10)
                self.assertEqual("".join(chunks), sample)

    def test_chunks_respect_limit_for_normal_paragraphs(self):
        source = "第一段。\n第二段。\n第三段。\n第四段。\n"
        chunks = make_chunks(source, maximum=12)
        self.assertTrue(all(len(chunk) <= 12 for chunk in chunks))
        self.assertEqual("".join(chunks), source)

    def test_split_ending_preserves_windows_newlines(self):
        self.assertEqual(split_ending("一段文字\r\n"), ("一段文字", "\r\n"))
        self.assertEqual(split_ending("一段文字\n"), ("一段文字", "\n"))
        self.assertEqual(split_ending("一段文字"), ("一段文字", ""))

    def test_prompt_includes_matching_glossary_only(self):
        prompt = make_instructions(
            {"吴邪": "Ngô Tà", "张起灵": "Trương Khởi Linh", "不出现": "Không xuất hiện"},
            "吴邪走进房间。",
        )
        self.assertIn("吴邪 → Ngô Tà", prompt)
        self.assertNotIn("不出现 → 不出现", prompt)
        self.assertNotIn("Không xuất hiện", prompt)


if __name__ == "__main__":
    unittest.main()
