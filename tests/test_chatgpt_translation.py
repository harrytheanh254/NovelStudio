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


class ClipboardChunkingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import importlib.util
        from pathlib import Path
        module_path = Path(__file__).resolve().parents[1] / "app-desktop" / "main.py"
        spec = importlib.util.spec_from_file_location("novelstudio_main_for_tests", module_path)
        cls.app_module = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        spec.loader.exec_module(cls.app_module)

    def test_clipboard_chunking_preserves_source_exactly(self):
        samples = [
            "第一段。\n\n第二段。\r\n\r\n第三段。\n",
            "这是一大段没有换行的故事。" * 1500,
            "他说：“等等！”她停了下来。\r\n下一段开始。\r\n\r\n最后一段。",
            "",
        ]
        for sample in samples:
            with self.subTest(length=len(sample)):
                chunks = self.app_module.split_text_for_clipboard_translation(sample, max_chars=600)
                self.assertEqual("".join(chunk for chunk, _separator in chunks), sample)
                self.assertEqual(len(chunks), len(chunks))

    def test_clipboard_chunking_separators_are_known_line_breaks_or_spaces(self):
        source = ("第一段。\n\n" + "没有换行的句子。" * 100 + "\n第二段。") * 20
        chunks = self.app_module.split_text_for_clipboard_translation(source, max_chars=700)
        self.assertTrue(all(separator in (" ", "\r\n\r\n", "\n\n", "\r\n", "\n", "\r", "") 
                            for _chunk, separator in chunks))
        self.assertEqual("".join(chunk for chunk, _separator in chunks), source)


class ThreeChapterBatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import importlib.util
        from pathlib import Path
        module_path = Path(__file__).resolve().parents[1] / "app-desktop" / "main.py"
        spec = importlib.util.spec_from_file_location("novelstudio_main_for_chapter_tests", module_path)
        cls.app_module = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        spec.loader.exec_module(cls.app_module)

    def test_fifteen_chapters_become_five_batches_of_three(self):
        source = "".join(
            f"第{number}章 标题{number}\n正文{number}的内容。\n\n"
            for number in range(1, 16)
        )
        chapter_count, batches = self.app_module.split_novel_into_batches(source, chapters_per_batch=3)
        self.assertEqual(chapter_count, 15)
        self.assertEqual(len(batches), 5)
        self.assertEqual("".join(batches), source)
        for batch_index, batch in enumerate(batches):
            expected_numbers = range(batch_index * 3 + 1, batch_index * 3 + 4)
            for number in expected_numbers:
                self.assertIn(f"第{number}章", batch)
            self.assertEqual(len(self.app_module.CHAPTER_HEADING_RE.findall(batch)), 3)

    def test_chinese_number_chapters_are_detected(self):
        source = "第十一章\n第一章内容。\n\n第十二章 标题\n第二章内容。\n\n第十三章\n第三章内容。"
        count, batches = self.app_module.split_novel_into_batches(source, 3)
        self.assertEqual(count, 3)
        self.assertEqual(len(batches), 1)
        self.assertEqual(batches[0], source)

    def test_missing_chapter_headings_is_reported(self):
        with self.assertRaisesRegex(ValueError, "Không nhận ra tiêu đề chương"):
            self.app_module.split_novel_into_batches("Chỉ có văn bản mà không có tiêu đề chương.")
