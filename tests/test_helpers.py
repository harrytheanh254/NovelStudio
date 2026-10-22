import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_translation_split_preserves_content():
    module = load_module("translate_hachimi", ROOT / "scripts" / "translate_hachimi.py")
    source = "这是第一句话。" + ("没有标点的长文本" * 100)
    parts = module.split_long_paragraph(source, max_chars=80)
    assert "".join(parts) == source
    assert all(len(part) <= 80 for part in parts)


def test_glossary_protects_and_restores_character_names():
    module = load_module("translate_hachimi_glossary", ROOT / "scripts" / "translate_hachimi.py")
    source = "吴邪遇见张起灵，胖子也来了。"
    glossary = {"吴邪": "Ngô Tà", "张起灵": "Trương Khởi Linh", "胖子": "Bàn Tử"}
    protected, marker_targets = module.protect_glossary(source, glossary)
    assert "吴邪" not in protected
    assert "张起灵" not in protected
    restored = module.restore_glossary(protected, marker_targets)
    assert restored == "Ngô Tà遇见Trương Khởi Linh，Bàn Tử也来了。"

    marker = next(iter(marker_targets))
    spaced_marker = " ".join(marker)
    assert module.restore_glossary(spaced_marker, {marker: "Ngô Tà"}) == "Ngô Tà"


def test_per_novel_glossaries_protect_core_terms():
    module = load_module("translate_hachimi_profiles", ROOT / "scripts" / "translate_hachimi.py")
    cases = [
        ("glossary_lam_thanh.json", "颜时序", "Nhan Thì Tự"),
        ("glossary_vot_thi_nhan.json", "李追远", "Lý Truy Viễn"),
    ]
    for filename, source_term, target_term in cases:
        glossary = module.load_glossary(ROOT / "config" / filename)
        assert glossary[source_term] == target_term
        protected, targets = module.protect_glossary("人物：" + source_term, glossary)
        restored = module.restore_glossary(protected, targets)
        assert restored == "人物：" + target_term


def test_translation_never_sends_glossary_term_to_model():
    module = load_module("translate_hachimi_segmentation", ROOT / "scripts" / "translate_hachimi.py")
    glossary = {"颜时序": "Nhan Thì Tự"}
    seen = []

    def fake_translate(fragment):
        seen.append(fragment)
        return f"<{fragment}>"

    translated = module.translate_glossary_line("颜时序看向前方。", glossary, fake_translate)
    assert "颜时序" not in seen
    assert translated == "Nhan Thì Tự <看向前方。>"


def test_ffmpeg_concat_quote_handles_apostrophe():
    module = load_module("merge_audio", ROOT / "scripts" / "merge_audio.py")
    quoted = module.concat_quote(Path("D:/NovelStudio/author's story/chapter 1.mp3"))
    assert quoted.startswith("'") and quoted.endswith("'")
    assert "'\\''" in quoted


def test_audio_output_filename_keeps_vietnamese_and_removes_invalid_characters():
    module = load_module("app_main", ROOT / "app-desktop" / "main.py")
    stem = module.NovelStudioApp._safe_audio_stem('Lâm Thánh: Chương 1/2?')
    assert "Lâm Thánh" in stem
    assert all(ch not in stem for ch in '<>:"/\\|?*')


if __name__ == "__main__":
    test_translation_split_preserves_content()
    test_per_novel_glossaries_protect_core_terms()
    test_translation_never_sends_glossary_term_to_model()
    test_glossary_protects_and_restores_character_names()
    test_audio_output_filename_keeps_vietnamese_and_removes_invalid_characters()
    test_ffmpeg_concat_quote_handles_apostrophe()
    print("Helper tests passed.")
