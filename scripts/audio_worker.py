from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

VOICE_IDS = {
    "Nam Minh": "vi-VN-NamMinhNeural",
    "Hoài My": "vi-VN-HoaiMyNeural",
    "vi-VN-NamMinhNeural": "vi-VN-NamMinhNeural",
    "vi-VN-HoaiMyNeural": "vi-VN-HoaiMyNeural",
}


def rate_percent(rate: str) -> str:
    value = float(rate)
    if value < 0.5 or value > 2.0:
        raise ValueError("Tốc độ cần nằm trong khoảng 0.5 đến 2.0.")
    return f"{round((value - 1.0) * 100):+d}%"


async def run(text: str, voice: str, rate: str, output: Path, attempts: int) -> None:
    try:
        import edge_tts
    except ImportError as exc:
        raise RuntimeError("Chưa có edge-tts trong môi trường audio. Hãy cài requirements của Vietnamese-Long-Audio-TTS.") from exc

    voice_id = VOICE_IDS.get(voice)
    if not voice_id:
        raise ValueError(f"Giọng không được hỗ trợ: {voice}")
    rate_value = rate_percent(rate)
    output.parent.mkdir(parents=True, exist_ok=True)
    partial = output.with_name(output.stem + ".partial" + output.suffix)
    last_error = None
    for attempt in range(1, attempts + 1):
        partial.unlink(missing_ok=True)
        try:
            communicator = edge_tts.Communicate(text=text, voice=voice_id, rate=rate_value)
            await communicator.save(str(partial))
            if not partial.is_file() or partial.stat().st_size == 0:
                raise RuntimeError("Edge-TTS không tạo ra MP3 hợp lệ.")
            os.replace(partial, output)
            return
        except Exception as exc:
            last_error = exc
            partial.unlink(missing_ok=True)
            print(f"[RETRY] Lần thử {attempt}/{attempts}: {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
            if attempt < attempts:
                await asyncio.sleep((3, 8)[min(attempt - 1, 1)])
    raise RuntimeError(f"Thất bại sau {attempts} lần thử. Lỗi cuối: {type(last_error).__name__}: {last_error}") from last_error


def main() -> int:
    parser = argparse.ArgumentParser(description="Tạo một đoạn MP3 bằng Edge-TTS.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--voice", default="Nam Minh")
    parser.add_argument("--rate", default="1.0")
    parser.add_argument("--attempts", type=int, default=3)
    args = parser.parse_args()
    source = Path(args.input)
    output = Path(args.output)
    try:
        text = source.read_text(encoding="utf-8-sig").strip()
        if not text:
            raise ValueError("Đoạn văn bản trống.")
        asyncio.run(run(text, args.voice, args.rate, output, args.attempts))
        print(f"[SUCCESS] {output} ({output.stat().st_size} bytes)", flush=True)
        return 0
    except Exception as exc:
        print(f"[ERROR] {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
