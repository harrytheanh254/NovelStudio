import importlib.util
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / 'app-desktop' / 'main.py'
SPEC = importlib.util.spec_from_file_location('novelstudio_modes_test', MODULE_PATH)
APP = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(APP)


class LiteraryModesTests(unittest.TestCase):
    def test_raw_mode_has_translation_rules(self):
        prompt = APP.build_clipboard_translation_prompt(
            '第1章\\n吴邪走进房间。', {'吴邪': 'Ngô Tà'},
            source_mode='Dịch raw Trung', novel_title='Thử nghiệm', batch_number=1, batch_total=5,
        )
        self.assertIn('DỊCH RAW TIẾNG TRUNG', prompt)
        self.assertIn('Ngô Tà', prompt)
        self.assertIn('không bám máy móc', prompt)
        self.assertIn('Không dùng chữ đậm', prompt)
        self.assertIn('<<<BEGIN_STORY_TEXT>>>', prompt)

    def test_convert_mode_is_a_rewrite_not_translation(self):
        prompt = APP.build_clipboard_translation_prompt(
            'Chương 1\\nNgô Tà đi vào phòng.', {'吴邪': 'Ngô Tà'},
            source_mode='Viết lại convert', novel_title='Thử nghiệm',
        )
        self.assertIn('VIẾT LẠI BẢN CONVERT TIẾNG VIỆT', prompt)
        self.assertIn('KHÔNG dịch lại từ tiếng Trung', prompt)
        self.assertIn('PS / P.S.', prompt)
        self.assertIn('Không in đậm', prompt)

    def test_chinese_heading_with_fullwidth_comma_is_detected(self):
        source = "第一章，天崩開局\n「咳咳！」\n\n第二章，继续\n正文。"
        count, batches = APP.split_novel_into_batches(source, chapters_per_batch=3)
        chapters, labels = APP.split_novel_into_chapters(source)
        self.assertEqual(count, 2)
        self.assertEqual(len(batches), 1)
        self.assertEqual(batches[0], source)
        self.assertEqual(labels, ["第一章，天崩開局", "第二章，继续"])
        self.assertEqual("".join(chapters), source)

    def test_research_prompt_prepares_reference_without_translating(self):
        source = ''.join(f'第{n}章 标题{n}\\n吴邪出现。\\n\\n' for n in range(1, 16))
        prompt = APP.build_story_research_prompt(
            'Thử nghiệm', 'Dịch raw Trung', source, {'吴邪': 'Ngô Tà'},
        )
        self.assertIn('BƯỚC CHUẨN BỊ HỒ SƠ TRUYỆN', prompt)
        self.assertIn('Thử nghiệm', prompt)
        self.assertIn('Ngô Tà', prompt)
        self.assertIn('TIÊU ĐỀ VÀ TRÍCH ĐOẠN MẪU', prompt)
        self.assertIn('KHÔNG được dịch hay viết lại', prompt)
        self.assertNotIn('CHỈ DỊCH NGUYÊN VĂN TIẾNG TRUNG SAU ĐÂY', prompt)


class TranslationDraftPersistenceTests(unittest.TestCase):
    def test_translation_raw_and_vietnamese_drafts_restore_from_local_files(self):
        import tempfile
        from unittest.mock import patch

        class TextStub:
            def __init__(self, value):
                self.value = value

            def winfo_exists(self):
                return True

            def get(self, _start, _end):
                return self.value

        class VarStub:
            def __init__(self, value):
                self.value = value

            def get(self):
                return self.value

        class StatusStub:
            def set(self, value):
                self.value = value

        with tempfile.TemporaryDirectory() as temp_dir:
            draft_dir = Path(temp_dir)
            raw_path = draft_dir / "translation_raw_draft.txt"
            vi_path = draft_dir / "translation_vi_draft.txt"
            meta_path = draft_dir / "translation_session.json"
            with (
                patch.object(APP, "DRAFT_DIR", draft_dir),
                patch.object(APP, "TRANSLATION_RAW_DRAFT", raw_path),
                patch.object(APP, "TRANSLATION_VI_DRAFT", vi_path),
                patch.object(APP, "TRANSLATION_DRAFT_META", meta_path),
            ):
                app = APP.NovelStudioApp.__new__(APP.NovelStudioApp)
                app.translation_raw_draft = ""
                app.translation_vi_draft = ""
                app.translation_draft_meta = {}
                app._translation_draft_after_id = None
                app.raw_path = Path("D:/NovelStudio/data/raw/demo.txt")
                app.raw_box = TextStub("第一章，天崩開局\n正文")
                app.vi_box = TextStub("Chương một\nNội dung")
                app.glossary_profile_var = VarStub("Từ điển chung")
                app.story_title_var = VarStub("Truyện thử")
                app.translation_mode_var = VarStub("ChatGPT · Qua clipboard")
                app.source_mode_var = VarStub("Dịch raw Trung")
                app.status = StatusStub()

                app._save_translation_draft()
                self.assertEqual(raw_path.read_text(encoding="utf-8"), "第一章，天崩開局\n正文")
                self.assertEqual(vi_path.read_text(encoding="utf-8"), "Chương một\nNội dung")

                restored = APP.NovelStudioApp.__new__(APP.NovelStudioApp)
                restored.translation_raw_draft = ""
                restored.translation_vi_draft = ""
                restored.translation_draft_meta = {}
                restored.raw_path = None
                restored.status = StatusStub()
                restored._load_translation_draft()

                self.assertEqual(restored.translation_raw_draft, "第一章，天崩開局\n正文")
                self.assertEqual(restored.translation_vi_draft, "Chương một\nNội dung")
                self.assertEqual(restored.raw_path, Path("D:/NovelStudio/data/raw/demo.txt"))
                self.assertEqual(restored.translation_draft_meta["glossary_profile"], "Từ điển chung")
                self.assertEqual(restored.translation_draft_meta["story_title"], "Truyện thử")


if __name__ == '__main__':
    unittest.main()
