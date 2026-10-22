from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

MODEL_ID = "ngocdang83/HachimiMT-60-zh-vi"
DEFAULT_MAX_CHARS = 850


def read_utf8(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


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
        tokenizer, engine = load_engine(cache_dir)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        partial_path = output_path.with_suffix(output_path.suffix + ".partial")
        total = max(sum(1 for line in source.splitlines() if line.strip()), 1)
        def on_progress(done: int, _total: int) -> None:
            print(f"[PROGRESS] {done}/{total}", flush=True)
        translated = translate_text(source, tokenizer, engine, progress=on_progress)
        partial_path.write_text(translated, encoding="utf-8")
        partial_path.replace(output_path)
        print(f"[SUCCESS] Đã lưu bản dịch: {output_path}", flush=True)
        return 0
    except Exception as exc:
        print(f"[ERROR] {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
