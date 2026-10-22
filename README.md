# SẢNH TRUYỆN — NovelStudio

A lightweight Windows desktop prototype for managing a novel workflow: web capture, Chinese-to-Vietnamese translation, and Vietnamese audio generation.

## Status

This repository is an early development version, not a finished release. The UI is built with Python/Tkinter to remain suitable for low-memory PCs.

### Features planned / in development

- Open the real Chrome browser for WebToEpub capture.
- Convert EPUB files to TXT with `epub2txt`.
- Translate Chinese TXT to Vietnamese locally using a compact CPU model (separate setup required).
- Generate Vietnamese speech with Edge-TTS (internet connection required).
- Save intermediate TXT and MP3 files locally.

## Requirements

- Windows 10/11
- Python 3.12 recommended
- Google Chrome for WebToEpub
- Internet access for package installation and Edge-TTS

## Important

- The application is still being integrated and needs local testing.
- Do not commit books, personal TXT files, generated MP3s, credentials, API keys, virtual environments, or model weights.
- Check `THIRD_PARTY_NOTICES.md` before redistributing the app or its dependencies.

See `REPO_UPLOAD_GUIDE.md` for the next upload/setup steps once those files are present.