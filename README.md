# SẢNH TRUYỆN — NovelStudio (prototype v0.3)

A lightweight Windows desktop prototype for managing a novel workflow: web capture, Chinese-to-Vietnamese translation, and Vietnamese audio generation. The UI uses Python's built-in Tkinter and a dark steampunk palette for low-memory PCs.

**Status:** early development prototype, not a finished release. The code has been syntax-checked, but the integrated workflow still needs testing on the target Windows machine.

## Features

- **Cào truyện:** opens the real Chrome browser; lets you choose an EPUB and calls the local `epub2txt` executable. Install WebToEpub separately in Chrome.
- **Dịch truyện:** local Chinese-to-Vietnamese translation using HachimiMT-60 with CTranslate2 INT8 on CPU. Model weights are downloaded from Hugging Face on first use; no paid API key is required.
- **Tạo audio dài:** dán toàn bộ nội dung vào khung bên trái hoặc nạp một TXT, chọn giọng và tốc độ rồi nhấn **TẠO AUDIO**. Nút này chạy qua GitHub Actions để tạo một MP3 trên máy chủ rồi tự tải về máy. Khung bên phải hiển thị tiến trình, thời gian, kết quả và lỗi.
- Keeps raw TXT, translated TXT, EPUB and MP3 outputs in local project folders.

## Requirements

- Windows 10/11
- Python 3.12 recommended (scripts default to `D:\Python312\python.exe`)
- Git for Windows
- Google Chrome
- Internet for installing dependencies, downloading the translation model, and Edge-TTS synthesis

## Quick setup

1. Download this repository ZIP and extract it to `D:\NovelStudio`.
2. Clone the third-party tools under `D:\\NovelStudio\\vendor` (skip any that you already have). The long-audio repository is private, so sign in first using `gh auth login` and configure Git with `gh auth setup-git`:

   ```powershell
   cd D:\NovelStudio\vendor
   git clone https://github.com/dteviot/WebToEpub.git
   git clone https://github.com/ffreemt/epub2txt.git
   git clone https://github.com/harrytheanh254/Vietnamese-Long-Audio-TTS.git
   ```

3. Make sure `D:\NovelStudio\envs\epub2txt\Scripts\epub2txt.exe` exists and works.
4. Open PowerShell and run the audio setup script if needed:

   ```powershell
   powershell -ExecutionPolicy Bypass -File .\scripts\setup_audio.ps1
   ```

5. Update the local long-audio generator from the private repository. Sign in to GitHub CLI first with `gh auth login`. This downloads `generate_audio.py` and its matching dependencies. The updater itself does not upload novel text:

   ```powershell
   powershell -ExecutionPolicy Bypass -File .\scripts\update_long_audio_tts.ps1
   ```

6. Set up the local translation dependencies:

   ```powershell
   powershell -ExecutionPolicy Bypass -File .\scripts\setup_translation.ps1
   ```

7. Start the app by double-clicking `scripts\run_desktop.bat`, or run:

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

## Optional ChatGPT literary translation (experimental)

The translation screen includes an experimental **ChatGPT · Dịch văn học** mode based on OpenAI's official Sign in with ChatGPT flow for eligible open-source apps. It keeps HachimiMT-60 as the default local mode. ChatGPT mode uses the account's authorized Responses API access; it does not read or access the user's ChatGPT conversations.

- Run **scripts\\setup_translation.ps1** again after updating the project so the translation environment installs the JWT validation dependency.
- In **Dịch truyện**, choose **KẾT NỐI CHATGPT** and finish the OpenAI login/consent flow in the system browser. Windows DPAPI encrypts the local credential record for the signed-in Windows user. Use **NGẮT CHATGPT** to revoke the session and remove the local credential record.
- Select **ChatGPT · Dịch văn học** and press **BẮT ĐẦU DỊCH**. The app asks the account model catalog for an available model, translates the chapter in bounded chunks, passes the selected novel glossary, and saves the resulting TXT only after all chunks succeed.
- This plan-usage path is documented for eligible ChatGPT Plus/Pro accounts and workspaces; a successful identity sign-in alone does not guarantee permission to use the plan. Free accounts may not be eligible. The app reports permission and usage-limit errors and does not silently switch billing modes.
- ChatGPT mode sends each source chunk and matching glossary entries to OpenAI for translation. Requests set store=false and stream=true as required by this flow, but the text is still sent to an external service. Keep local mode selected for texts that must remain on the computer.
- The feature is experimental and must be tested with an account that has the required scope before relying on it for a full novel. Never commit credentials, raw novels, translations, or logs.

Official docs: https://developers.openai.com/siwc/token-sharing-open-source

## Known limitations

- Edge-TTS needs an internet connection and can fail due to connection issues or service-side limits.
- The desktop app processes queued chapter files sequentially to reduce pressure on Edge-TTS. It creates one named MP3 for each selected TXT file; a failed chapter is reported without blocking later queued chapters.
- Translation has no chapter-context memory; the glossary only protects exact phrases that are listed and does not make the small model's general prose more fluent. Select the correct novel profile before each translation.
- No Windows installer is included yet.
- The UI and backends still need end-to-end testing on the target PC.

## Repository hygiene

Do not commit novels, raw or translated TXT files, audio, downloaded model weights, virtual environments, caches, logs, credentials, or API tokens. These are excluded by `.gitignore`.

Repository: https://github.com/harrytheanh254/NovelStudio
