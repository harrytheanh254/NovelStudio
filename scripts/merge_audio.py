from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path


def concat_quote(path: Path) -> str:
    """Quote a path for the ffmpeg concat demuxer."""
    value = path.resolve().as_posix()
    # concat demuxer uses its own quoting syntax, not shell quoting.
    value = value.replace("'", "'\\''")
    return f"'{value}'"


def merge_mp3(inputs: list[Path], output: Path) -> None:
    if not inputs:
        raise ValueError("Không có phần MP3 nào để ghép.")
    missing = [str(path) for path in inputs if not path.is_file() or path.stat().st_size == 0]
    if missing:
        raise FileNotFoundError("Thiếu phần MP3: " + ", ".join(missing))

    try:
        import imageio_ffmpeg
    except ImportError as exc:
        raise RuntimeError(
            "Thiếu công cụ ghép MP3. Chạy lệnh cài imageio-ffmpeg được hướng dẫn trong README."
        ) from exc

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    output.parent.mkdir(parents=True, exist_ok=True)
    manifest = output.with_name(output.stem + ".concat.txt")
    partial = output.with_name(output.stem + ".partial.mp3")
    manifest.write_text(
        "".join(f"file {concat_quote(path)}\n" for path in inputs),
        encoding="utf-8",
    )
    try:
        command = [
            ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
            "-f", "concat", "-safe", "0", "-i", str(manifest),
            "-vn", "-map", "0:a:0", "-c:a", "libmp3lame",
            "-b:a", "128k", "-ar", "24000", "-ac", "1",
            str(partial),
        ]
        proc = subprocess.run(command, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=None)
        if proc.returncode != 0:
            raise RuntimeError((proc.stderr or proc.stdout or "FFmpeg không ghép được MP3.").strip())
        if not partial.is_file() or partial.stat().st_size == 0:
            raise RuntimeError("FFmpeg không tạo ra file MP3 hoàn chỉnh.")
        os.replace(partial, output)
    finally:
        manifest.unlink(missing_ok=True)
        partial.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Ghép nhiều phần audio thành một file MP3.")
    parser.add_argument("--output", required=True)
    parser.add_argument("--input", nargs="+", required=True)
    args = parser.parse_args()
    try:
        inputs = [Path(item).expanduser().resolve() for item in args.input]
        output = Path(args.output).expanduser().resolve()
        merge_mp3(inputs, output)
        print(f"[SUCCESS] Đã ghép {len(inputs)} phần thành: {output} ({output.stat().st_size} bytes)", flush=True)
        return 0
    except Exception as exc:
        print(f"[ERROR] {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
