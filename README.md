# SẢNH TRUYỆN — NovelStudio (prototype v0.3)

A lightweight Windows desktop prototype for managing a novel workflow: web capture, Chinese-to-Vietnamese translation, and Vietnamese audio generation. The UI uses Python's built-in Tkinter and a dark steampunk palette for low-memory PCs.

**Status:** early development prototype, not a finished release. The code has been syntax-checked, but the integrated workflow still needs testing on the target Windows machine.

## Features

- **Cào truyện:** opens the real Chrome browser for WebToEpub, then converts EPUB and common document formats to TXT. Direct local support includes TXT/Markdown, HTML/XHTML/XML, DOCX, ODT, RTF, FB2 and text-based PDFs. EPUB uses the bundled `epub2txt`; MOBI/AZW/AZW3 require Calibre, legacy DOC requires LibreOffice, and image-only/scanned PDFs need OCR which is not bundled. Source files are kept; existing raw TXT outputs are not overwritten.
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

- **Document conversion notes:** After updating, the translation environment installs `pypdf` via `requirements-translation.txt`. To enable PDF text extraction immediately, run `D:\NovelStudio\envs\translation\Scripts\python.exe -m pip install pypdf` if needed. Scanned PDFs contain page images rather than a text layer and require OCR; SẢNH TRUYỆN reports this rather than silently creating an empty TXT.

## Translation model

- Model: [HachimiMT-60 Chinese → Vietnamese](https://huggingface.co/ngocdang83/HachimiMT-60-zh-vi)
- Uses the CTranslate2 `ct2-int8_float32` model on CPU.
- The first translation downloads model files to `D:\NovelStudio\models\huggingface`.
- Machine translation can mistranslate prose, pronouns, and specialist terminology. Review output before publishing.
- Exact names/terms can be protected with JSON glossaries in `config/`. The translation screen lets you select a per-novel glossary: `glossary_lam_thanh.json`, `glossary_vot_thi_nhan.json`, or the shared `glossary_zh_vi.json`. Matching source phrases are replaced with placeholders before translation, then restored exactly afterward. These are starter dictionaries; add or correct entries as new characters and terms appear.
- Model card declares CC BY 4.0; see `THIRD_PARTY_NOTICES.md`.

## Optional ChatGPT literary translation (experimental)

The translation screen keeps HachimiMT-60 as the default local mode and offers two experimental ChatGPT paths. In **ChatGPT · Qua clipboard**, the raw pane has two source modes: **Dịch raw Trung** and **Viết lại convert**. The app first prepares a story-research prompt, then asks the user to paste ChatGPT's returned character/terminology reference into SẢNH TRUYỆN. Subsequent prompts use a mode-specific literary prompt, the selected glossary, and that reference profile. The app groups three chapters per batch, copies the next prompt after each accepted translation, and leaves the completed translation in the main Vietnamese pane for the user to save. It does not scrape or programmatically read ChatGPT's page/output.

- Run **scripts\\setup_translation.ps1** again after updating the project so the translation environment installs the JWT validation dependency.
- In **Dịch truyện**, choose **KẾT NỐI CHATGPT** and finish the OpenAI login/consent flow in the system browser. Windows DPAPI encrypts the local credential record for the signed-in Windows user. Use **NGẮT CHATGPT** to revoke the session and remove the local credential record.
- Select **ChatGPT · Dịch văn học** and press **BẮT ĐẦU DỊCH**. The app asks the account model catalog for an available model, translates the chapter in bounded chunks, passes the selected novel glossary, and saves the resulting TXT only after all chunks succeed.
- In the raw-pane source selector, choose **Dịch raw Trung** for original Chinese text or **Viết lại convert** for an existing Vietnamese convert draft. Set the story title if known and select the matching glossary profile.
- Before batch 1, the app creates a **story-research prompt** from the novel title, chapter headings, short excerpts, and current glossary. Send it in ChatGPT, copy ChatGPT's reference sheet, paste it into SẢNH TRUYỆN's **HỒ SƠ TRUYỆN** field, then click **LƯU HỒ SƠ & TẠO PROMPT LƯỢT 1**. The app uses that reference sheet in every batch prompt.
- The app detects chapter headings such as `第91章`, `第九十一章`, `Chapter 1`, or `Chương 1`, groups three chapters into each prompt, then opens ChatGPT with the prompt copied to the clipboard. After the answer is complete, manually copy it from ChatGPT and paste it at the end of the main Vietnamese translation pane in SẢNH TRUYỆN, then click **ĐÃ DÁN KẾT QUẢ · TIẾP TỤC**. The app announces and copies the next prompt. When all batches are accepted, the complete translation remains in the translation pane; click **LƯU BẢN DỊCH** to save the TXT. The clipboard mode does not read or scrape ChatGPT's webpage.
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
