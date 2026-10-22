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


def test_audio_split_does_not_drop_text():
    module = load_module("app_main", ROOT / "app-desktop" / "main.py")
    source = ("第一句话。第二句话！第三句话？\n\n" * 100).strip()
    parts = module.NovelStudioApp._split_audio_text(source, limit=90)
    compact = lambda s: "".join(s.split())
    assert compact("".join(parts)) == compact(source)
    assert all(len(part) <= 90 for part in parts)


if __name__ == "__main__":
    test_translation_split_preserves_content()
    test_per_novel_glossaries_protect_core_terms()
    test_glossary_protects_and_restores_character_names()
    test_audio_split_does_not_drop_text()
    print("Helper tests passed.")
