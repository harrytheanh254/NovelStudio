# SẢNH TRUYỆN — NovelStudio (prototype v0.3)

A lightweight Windows desktop prototype for managing a novel workflow: web capture, Chinese-to-Vietnamese translation, and Vietnamese audio generation. The UI uses Python's built-in Tkinter and a dark steampunk palette for low-memory PCs.

**Status:** early development prototype, not a finished release. The code has been syntax-checked, but the integrated workflow still needs testing on the target Windows machine.

## Features

- **Cào truyện:** opens the real Chrome browser; lets you choose an EPUB and calls the local `epub2txt` executable. Install WebToEpub separately in Chrome.
- **Dịch truyện:** local Chinese-to-Vietnamese translation using HachimiMT-60 with CTranslate2 INT8 on CPU. Model weights are downloaded from Hugging Face on first use; no paid API key is required.
- **Tạo audio:** Edge-TTS with Nam Minh or Hoài My. Long text is synthesized in smaller parts and automatically merged into one final MP3 per chapter using the bundled FFmpeg executable from `imageio-ffmpeg`.
- Keeps raw TXT, translated TXT, EPUB and MP3 outputs in local project folders.

## Requirements

- Windows 10/11
- Python 3.12 recommended (scripts default to `D:\Python312\python.exe`)
- Git for Windows
- Google Chrome
- Internet for installing dependencies, downloading the translation model, and Edge-TTS synthesis

## Quick setup

1. Download this repository ZIP and extract it to `D:\NovelStudio`.
2. Clone the third-party tools under `D:\NovelStudio\vendor` (skip any that you already have):

   ```powershell
   cd D:\NovelStudio\vendor
   git clone https://github.com/dteviot/WebToEpub.git
   git clone https://github.com/ffreemt/epub2txt.git
   git clone https://github.com/Tanphong254/Vietnamese-Long-Audio-TTS.git
   ```

3. Make sure `D:\NovelStudio\envs\epub2txt\Scripts\epub2txt.exe` exists and works.
4. Open PowerShell and run the audio setup script if needed:

   ```powershell
   powershell -ExecutionPolicy Bypass -File .\scripts\setup_audio.ps1
   ```

5. Set up the local translation dependencies:

   ```powershell
   powershell -ExecutionPolicy Bypass -File .\scripts\setup_translation.ps1
   ```

6. Start the app by double-clicking `scripts\run_desktop.bat`, or run:

   ```powershell
   & "D:\Python312\python.exe" "D:\NovelStudio\app-desktop\main.py"
   ```

If your Python 3.12 path differs, edit the `$Python` variable in the setup scripts and the `PYTHON` variable in `run_desktop.bat`.

## Translation model

- Model: [HachimiMT-60 Chinese → Vietnamese](https://huggingface.co/ngocdang83/HachimiMT-60-zh-vi)
- Uses the CTranslate2 `ct2-int8_float32` model on CPU.
- The first translation downloads model files to `D:\NovelStudio\models\huggingface`.
- Machine translation can mistranslate prose, pronouns, and specialist terminology. Review output before publishing.
- Exact names/terms can be protected with JSON glossaries in `config/`. The translation screen lets you select a per-novel glossary: `glossary_lam_thanh.json`, `glossary_vot_thi_nhan.json`, or the shared `glossary_zh_vi.json`. Matching source phrases are replaced with placeholders before translation, then restored exactly afterward. These are starter dictionaries; add or correct entries as new characters and terms appear.
- Model card declares CC BY 4.0; see `THIRD_PARTY_NOTICES.md`.

## Known limitations

- Edge-TTS needs an internet connection and can fail due to connection issues or service-side limits.
- When any speech chunk fails, the app does not create an incomplete final MP3; successful temporary chunks are preserved under the job's `_parts` folder so the failure can be inspected.
- Translation has no chapter-context memory; the glossary only protects exact phrases that are listed and does not make the small model's general prose more fluent. Select the correct novel profile before each translation.
- No Windows installer is included yet.
- The UI and backends still need end-to-end testing on the target PC.

## Repository hygiene

Do not commit novels, raw or translated TXT files, audio, downloaded model weights, virtual environments, caches, logs, credentials, or API tokens. These are excluded by `.gitignore`.

Repository: https://github.com/harrytheanh254/NovelStudio
