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


def test_audio_split_does_not_drop_text():
    module = load_module("app_main", ROOT / "app-desktop" / "main.py")
    source = ("第一句话。第二句话！第三句话？\n\n" * 100).strip()
    parts = module.NovelStudioApp._split_audio_text(source, limit=90)
    compact = lambda s: "".join(s.split())
    assert compact("".join(parts)) == compact(source)
    assert all(len(part) <= 90 for part in parts)


if __name__ == "__main__":
    test_translation_split_preserves_content()
    test_audio_split_does_not_drop_text()
    print("Helper tests passed.")
