from __future__ import annotations

import argparse
import json
import os
import re
import sys
import traceback
from pathlib import Path

# Avoid OpenBLAS allocating a worker pool for every reported CPU core on constrained PCs.
# Set these before transformers/numpy or other libraries load a BLAS runtime.
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["GOTO_NUM_THREADS"] = "1"

# Windows consoles may use a legacy code page that cannot print Vietnamese text.
# Force UTF-8 for status messages and warnings; replace any unencodable third-party output.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

MODEL_ID = "ngocdang83/HachimiMT-60-zh-vi"
DEFAULT_MAX_CHARS = 850
ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_GLOSSARY_PATH = ROOT_DIR / "config" / "glossary_zh_vi.json"


def read_utf8(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def load_glossary(path: Path) -> dict[str, str]:
    """Load exact Chinese-to-Vietnamese terms. Missing glossary files mean no substitutions."""
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Không đọc được từ điển {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("Từ điển phải là JSON dạng { \"từ tiếng Trung\": \"cách viết tiếng Việt\" }.")
    glossary: dict[str, str] = {}
    for source, target in data.items():
        if not isinstance(source, str) or not isinstance(target, str):
            continue
        source, target = source.strip(), target.strip()
        if source and target:
            glossary[source] = target
    return glossary


def protect_glossary(source: str, glossary: dict[str, str]) -> tuple[str, dict[str, str]]:
    """Replace exact glossary terms with stable ASCII markers before machine translation."""
    protected = source
    marker_to_target: dict[str, str] = {}
    # Replace longer names first so a short alias cannot consume part of a full name.
    terms = sorted(glossary.items(), key=lambda item: len(item[0]), reverse=True)
    next_id = 1
    for source_term, target_term in terms:
        if source_term not in protected:
            continue
        marker = f"ZXQTERM{next_id:05d}QXZ"
        next_id += 1
        protected = protected.replace(source_term, marker)
        marker_to_target[marker] = target_term
    return protected, marker_to_target


def restore_glossary(translated: str, marker_to_target: dict[str, str]) -> str:
    """Restore glossary terms, allowing whitespace if the tokenizer split a marker."""
    result = translated
    for marker, target in marker_to_target.items():
        pattern = r"\s*".join(re.escape(char) for char in marker)
        result = re.sub(pattern, lambda _match, value=target: value, result, flags=re.IGNORECASE)
    return result


def split_long_paragraph(text: str, max_chars: int = DEFAULT_MAX_CHARS) -> list[str]:
    """Split long Chinese paragraphs at punctuation when possible, never drop text."""
    text = text.strip()
    if not text:
        return [""]
    if len(text) <= max_chars:
        return [text]

    sentences = re.split(r"(?<=[。！？!?；;])", text)
    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        if not sentence:
            continue
        if len(sentence) > max_chars:
            if current:
                chunks.append(current)
                current = ""
            for start in range(0, len(sentence), max_chars):
                chunks.append(sentence[start:start + max_chars])
            continue
        if current and len(current) + len(sentence) > max_chars:
            chunks.append(current)
            current = sentence
        else:
            current += sentence
    if current:
        chunks.append(current)
    return chunks or [text]


def restore_line_ending(line: str) -> tuple[str, str]:
    if line.endswith("\r\n"):
        return line[:-2], "\r\n"
    if line.endswith("\n"):
        return line[:-1], "\n"
    if line.endswith("\r"):
        return line[:-1], "\r"
    return line, ""


def load_engine(cache_dir: Path):
    try:
        import ctranslate2
        from huggingface_hub import snapshot_download
        from transformers import AutoTokenizer
    except ImportError as exc:
        raise RuntimeError(
            "Thiếu thư viện dịch. Hãy chạy scripts\\setup_translation.ps1 trước."
        ) from exc

    cache_dir.mkdir(parents=True, exist_ok=True)
    print("[STATUS] Đang tải/đọc mô hình dịch lần đầu; lần sau sẽ dùng bản đã lưu.", flush=True)
    model_path = Path(snapshot_download(
        repo_id=MODEL_ID,
        cache_dir=str(cache_dir),
        allow_patterns=[
            "config.json", "source.spm", "target.spm", "vocab.json",
            "tokenizer_config.json", "special_tokens_map.json", "ct2-int8_float32/*",
        ],
    ))
    model_dir = model_path / "ct2-int8_float32"
    if not model_dir.is_dir():
        raise RuntimeError(f"Không tìm thấy mô hình CTranslate2: {model_dir}")
    tokenizer = AutoTokenizer.from_pretrained(model_path)
    engine = ctranslate2.Translator(
        str(model_dir),
        device="cpu",
        compute_type="int8_float32",
        inter_threads=1,
        intra_threads=2,
    )
    return tokenizer, engine


def translate_piece(text: str, tokenizer, engine) -> str:
    encoded = tokenizer(text, add_special_tokens=True)
    tokens = tokenizer.convert_ids_to_tokens(encoded.input_ids)
    result = engine.translate_batch(
        [tokens],
        beam_size=2,
        max_decoding_length=320,
    )[0]
    token_ids = tokenizer.convert_tokens_to_ids(result.hypotheses[0])
    return tokenizer.decode(token_ids, skip_special_tokens=True).strip()


def translate_glossary_line(body: str, glossary: dict[str, str], translate_fragment) -> str:
    """Translate around exact glossary hits; glossary terms themselves never enter the model."""
    terms = sorted(glossary.keys(), key=len, reverse=True)
    if not terms:
        return translate_fragment(body)
    pattern = re.compile("(" + "|".join(re.escape(term) for term in terms) + ")")
    pieces = pattern.split(body)
    if len(pieces) == 1:
        return translate_fragment(body)

    output = ""
    opening_punctuation = set("（([{「『“‘《〈【〔〖〘〚")
    closing_punctuation = set("，。！？；：,.!?;:、…）)]}”’」』》〉】〕〗〙〛")
    for piece in pieces:
        if not piece:
            continue
        if piece in glossary:
            translated_piece = glossary[piece]
        elif not piece.strip():
            continue
        elif all(char.isspace() or __import__("unicodedata").category(char).startswith("P")
                 for char in piece):
            translated_piece = piece.strip()
        else:
            translated_piece = translate_fragment(piece).strip()
        if not translated_piece:
            continue
        if not output:
            output = translated_piece
            continue

        left = output.rstrip()
        right = translated_piece.lstrip()
        if not left or not right:
            output = left + right
        elif right[0] in closing_punctuation:
            output = left + right
        elif left[-1] in opening_punctuation:
            output = left + right
        else:
            # Vietnamese needs a word boundary around restored names, unlike Chinese source text.
            output = left + " " + right
    return output


def translate_text_with_glossary(source: str, tokenizer, engine, glossary: dict[str, str], progress=None) -> str:
    """Translate text while preserving exact character/term spellings from the selected glossary."""
    lines = source.splitlines(keepends=True)
    if not lines and source:
        lines = [source]
    nonblank_count = sum(1 for line in lines if restore_line_ending(line)[0].strip())
    completed = 0
    output: list[str] = []

    def translate_fragment(fragment: str) -> str:
        return translate_text(fragment, tokenizer, engine).strip()

    for line in lines:
        body, ending = restore_line_ending(line)
        if not body.strip():
            output.append(line)
            continue
        if any(term in body for term in glossary):
            translated = translate_glossary_line(body, glossary, translate_fragment)
        else:
            translated = translate_fragment(body)
        output.append(translated + ending)
        completed += 1
        if progress:
            progress(completed, max(nonblank_count, 1))
    return "".join(output)


def translate_text(source: str, tokenizer, engine, progress=None) -> str:
    lines = source.splitlines(keepends=True)
    if not lines and source:
        lines = [source]
    nonblank_count = sum(1 for line in lines if restore_line_ending(line)[0].strip())
    completed = 0
    output: list[str] = []
    for line in lines:
        body, ending = restore_line_ending(line)
        if not body.strip():
            output.append(line)
            continue
        pieces = split_long_paragraph(body)
        translated_pieces = [translate_piece(piece, tokenizer, engine) for piece in pieces]
        translated = " ".join(piece for piece in translated_pieces if piece)
        output.append(translated + ending)
        completed += 1
        if progress:
            progress(completed, max(nonblank_count, 1))
    return "".join(output)


def main() -> int:
    parser = argparse.ArgumentParser(description="Dịch TXT tiếng Trung sang tiếng Việt bằng HachimiMT-60 (CPU INT8).")
    parser.add_argument("--input", required=True, help="TXT đầu vào, mã hóa UTF-8")
    parser.add_argument("--output", required=True, help="TXT bản dịch đầu ra")
    parser.add_argument("--cache-dir", required=True, help="Thư mục cache mô hình trên ổ D")
    parser.add_argument("--glossary", default=str(DEFAULT_GLOSSARY_PATH), help="Từ điển thuật ngữ Trung -> Việt dạng JSON")
    args = parser.parse_args()

    source_path = Path(args.input).expanduser().resolve()
    output_path = Path(args.output).expanduser().resolve()
    cache_dir = Path(args.cache_dir).expanduser().resolve()
    if not source_path.is_file():
        print(f"[ERROR] Không tìm thấy file đầu vào: {source_path}", file=sys.stderr, flush=True)
        return 2
    try:
        source = read_utf8(source_path)
        if not source.strip():
            raise ValueError("File TXT đang trống.")
        glossary = load_glossary(Path(args.glossary).expanduser().resolve())
        matched_terms = sum(1 for term in glossary if term in source)
        print(f"[STATUS] Từ điển đã nạp: {len(glossary)} mục; khớp trong văn bản này: {matched_terms} mục.", flush=True)
        tokenizer, engine = load_engine(cache_dir)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        partial_path = output_path.with_suffix(output_path.suffix + ".partial")
        total = max(sum(1 for line in source.splitlines() if line.strip()), 1)
        def on_progress(done: int, _total: int) -> None:
            print(f"[PROGRESS] {done}/{total}", flush=True)
        translated = translate_text_with_glossary(source, tokenizer, engine, glossary, progress=on_progress)
        partial_path.write_text(translated, encoding="utf-8")
        partial_path.replace(output_path)
        print(f"[SUCCESS] Đã lưu bản dịch: {output_path}", flush=True)
        return 0
    except Exception as exc:
        # Keep the full traceback in UTF-8 so the desktop app can diagnose failures
        # even when a third-party library hits a Windows legacy-code-page issue.
        try:
            log_path = ROOT_DIR / "logs" / "translation_error.log"
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_path.write_text(traceback.format_exc(), encoding="utf-8")
        except Exception:
            pass
        print(f"[ERROR] {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
