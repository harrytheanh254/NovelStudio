from __future__ import annotations

import base64
import gzip
import json
import os
import shutil
import subprocess
import threading
import uuid
import time
import webbrowser
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

APP_TITLE = "SẢNH TRUYỆN"
BG = "#090707"
SIDEBAR = "#100B0A"
PANEL = "#17100F"
PANEL2 = "#201513"
INK = "#F5E9DE"
MUTED = "#B6A095"
DIM = "#806D63"
RED = "#D21F32"
RED_HOVER = "#F23848"
BRASS = "#B97848"
BORDER = "#573025"
GREEN = "#69C987"
YELLOW = "#E5B15A"
FONT = "Segoe UI"

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
EPUB_DIR = DATA_DIR / "epub"
RAW_DIR = DATA_DIR / "raw"
TRANSLATED_DIR = DATA_DIR / "translated"
AUDIO_DIR = DATA_DIR / "audio"
TEMP_DIR = ROOT_DIR / "temp"
MODEL_CACHE_DIR = ROOT_DIR / "models" / "huggingface"
GLOSSARY_DIR = ROOT_DIR / "config"
GLOSSARY_PROFILES = {
    "Lâm Thánh": GLOSSARY_DIR / "glossary_lam_thanh.json",
    "Vớt Thi Nhân": GLOSSARY_DIR / "glossary_vot_thi_nhan.json",
    "Từ điển chung": GLOSSARY_DIR / "glossary_zh_vi.json",
}
EPUB2TXT_EXE = ROOT_DIR / "envs" / "epub2txt" / "Scripts" / "epub2txt.exe"
TRANSLATION_PYTHON = ROOT_DIR / "envs" / "translation" / "Scripts" / "python.exe"
AUDIO_PYTHON = ROOT_DIR / "envs" / "audio-tts" / "Scripts" / "python.exe"
TRANSLATION_SCRIPT = ROOT_DIR / "scripts" / "translate_hachimi.py"
AUDIO_WORKER_SCRIPT = ROOT_DIR / "scripts" / "audio_worker.py"
AUDIO_TTS_GENERATOR = ROOT_DIR / "vendor" / "Vietnamese-Long-Audio-TTS" / "generate_audio.py"
MERGE_AUDIO_SCRIPT = ROOT_DIR / "scripts" / "merge_audio.py"
GITHUB_AUDIO_REPO = os.environ.get(
    "NOVELSTUDIO_GITHUB_AUDIO_REPO",
    "harrytheanh254/Vietnamese-Long-Audio-TTS",
).strip()
GITHUB_AUDIO_REF = os.environ.get("NOVELSTUDIO_GITHUB_AUDIO_REF", "main").strip() or "main"
GITHUB_AUDIO_WORKFLOW = "generate_audio.yml"
GITHUB_AUDIO_MAX_ENCODED_CHARS = 58000

for folder in (EPUB_DIR, RAW_DIR, TRANSLATED_DIR, AUDIO_DIR, TEMP_DIR):
    folder.mkdir(parents=True, exist_ok=True)


class RoundedButton(tk.Canvas):
    """A simple rounded button drawn on Canvas, without third-party GUI packages."""

    def __init__(self, parent, text, command, primary=False, width=None):
        self.text = text
        self.command = command
        self.primary = primary
        self.fill = RED if primary else PANEL2
        self.hover = RED_HOVER if primary else "#2A1718"
        self.current = self.fill
        px_width = width or max(112, len(text) * 8 + 30)
        super().__init__(parent, width=px_width, height=38, bg=parent.cget("bg"),
                         highlightthickness=0, bd=0, cursor="hand2")
        self.bind("<Configure>", self.draw)
        self.bind("<Enter>", self.on_enter)
        self.bind("<Leave>", self.on_leave)
        self.bind("<Button-1>", self.on_click)
        self.draw()

    def draw(self, _event=None):
        self.delete("all")
        w = max(self.winfo_width(), int(self.cget("width")))
        h = max(self.winfo_height(), 38)
        r = h // 2
        points = [r, 1, w-r, 1, w-1, 1, w-1, r, w-1, h-r, w-1, h-1,
                  r, h-1, 1, h-1, 1, r, 1, 1]
        self.create_polygon(points, smooth=True, splinesteps=24, fill=self.current,
                            outline=RED if self.primary else BORDER, width=1)
        self.create_text(w // 2, h // 2, text=self.text, fill=INK,
                         font=(FONT, 9, "bold" if self.primary else "normal"))

    def on_enter(self, _event=None):
        self.current = self.hover
        self.draw()

    def on_leave(self, _event=None):
        self.current = self.fill
        self.draw()

    def on_click(self, _event=None):
        if callable(self.command):
            self.command()


class NovelStudioApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("1180x760")
        self.root.minsize(980, 640)
        self.root.configure(bg=BG)
        self.status = tk.StringVar(value="Sẵn sàng · File được lưu trên máy bạn")
        self.raw_path: Path | None = None
        self.audio_path: Path | None = None
        self.audio_paths: list[Path] = []
        self.translation_running = False
        self.audio_running = False
        self.audio_queue: list[dict] = []
        self.audio_outputs: list[Path] = []
        self.audio_history: list[dict] = []
        self.audio_list_paths: dict[int, Path] = {}
        self._audio_status_after_id: str | None = None
        self._audio_spinner_angle = 0
        self.current_page = "home"
        self._configure_styles()
        self._shell()
        self.show_home()

    def _configure_styles(self):
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Dark.TCombobox", fieldbackground=PANEL2, background=PANEL2,
                        foreground=INK, arrowcolor=BRASS, padding=7)
        style.map("Dark.TCombobox", fieldbackground=[("readonly", PANEL2)],
                  foreground=[("readonly", INK)], selectbackground=[("readonly", RED)])

    def _shell(self):
        top = tk.Frame(self.root, bg="#0D0908", height=56,
                       highlightbackground="#3B211B", highlightthickness=1)
        top.pack(fill="x")
        top.pack_propagate(False)
        tk.Label(top, text="◈  SẢNH TRUYỆN", bg="#0D0908", fg=INK,
                 font=(FONT, 14, "bold")).pack(side="left", padx=20)
        tk.Label(top, text="ĐỌC  ·  DỊCH  ·  NGHE", bg="#0D0908", fg=BRASS,
                 font=(FONT, 9, "bold")).pack(side="left", padx=18)
        tk.Label(top, text="LOCAL WORKSPACE  ●", bg="#0D0908", fg=GREEN,
                 font=(FONT, 8, "bold")).pack(side="right", padx=20)

        body = tk.Frame(self.root, bg=BG)
        body.pack(fill="both", expand=True)
        body.grid_rowconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=1)
        side = tk.Frame(body, bg=SIDEBAR, width=188,
                        highlightbackground="#2F1C17", highlightthickness=1)
        side.grid(row=0, column=0, sticky="nsw")
        side.grid_propagate(False)
        tk.Label(side, text="WORKSHOP", bg=SIDEBAR, fg=DIM,
                 font=(FONT, 8, "bold")).pack(anchor="w", padx=18, pady=(23, 12))
        self.nav = {}
        for key, label in (("home", "⌂  Tổng quan"), ("scrape", "⇩  Cào truyện"),
                           ("translate", "文  Dịch truyện"), ("audio", "♫  Tạo audio")):
            btn = tk.Button(side, text=label, anchor="w", bd=0, padx=16, pady=11,
                            bg=SIDEBAR, fg=MUTED, activebackground=PANEL2,
                            activeforeground=INK, font=(FONT, 10), cursor="hand2",
                            command=lambda k=key: self.navigate(k))
            btn.pack(fill="x", padx=8, pady=3)
            self.nav[key] = btn
        tk.Frame(side, bg=BORDER, height=1).pack(fill="x", padx=16, pady=16)
        tk.Label(side, text="THƯ MỤC DỮ LIỆU", bg=SIDEBAR, fg=DIM,
                 font=(FONT, 8, "bold")).pack(anchor="w", padx=17, pady=(0, 8))
        for name, path in (("EPUB", EPUB_DIR), ("RAW TXT", RAW_DIR),
                           ("BẢN DỊCH", TRANSLATED_DIR), ("AUDIO", AUDIO_DIR)):
            tk.Button(side, text="▸  " + name, anchor="w", bd=0, padx=16, pady=6,
                      bg=SIDEBAR, fg=DIM, activebackground=PANEL2, activeforeground=INK,
                      font=(FONT, 8), command=lambda p=path: self.open_folder(p)).pack(fill="x", padx=8)
        tk.Label(side, text="STEAMPUNK EDITION\nv0.3 · LOCAL", bg=SIDEBAR, fg="#59443B",
                 font=(FONT, 8), justify="left").pack(side="bottom", anchor="w", padx=17, pady=16)

        self.content = tk.Frame(body, bg=BG)
        self.content.grid(row=0, column=1, sticky="nsew")
        self.content.grid_rowconfigure(0, weight=1)
        self.content.grid_columnconfigure(0, weight=1)
        bottom = tk.Label(self.root, textvariable=self.status, anchor="w",
                          bg="#0D0908", fg=MUTED, padx=14, pady=7,
                          font=(FONT, 9), highlightbackground="#3B211B", highlightthickness=1)
        bottom.pack(fill="x")

    def navigate(self, name):
        {"home": self.show_home, "scrape": self.show_scrape,
         "translate": self.show_translate, "audio": self.show_audio}.get(name, self.show_home)()

    def _select_nav(self, active):
        for key, btn in self.nav.items():
            btn.configure(bg=PANEL2 if key == active else SIDEBAR,
                          fg=INK if key == active else MUTED)

    def _clear(self, active):
        for child in self.content.winfo_children():
            child.destroy()
        self._select_nav(active)
        self.current_page = active
        frame = tk.Frame(self.content, bg=BG)
        frame.grid(row=0, column=0, sticky="nsew")
        frame.grid_columnconfigure(0, weight=1)
        return frame

    def _heading(self, parent, eyebrow, title, subtitle):
        tk.Label(parent, text=eyebrow.upper(), bg=BG, fg=BRASS,
                 font=(FONT, 8, "bold")).pack(anchor="w", padx=26, pady=(22, 4))
        tk.Label(parent, text=title, bg=BG, fg=INK,
                 font=(FONT, 22, "bold")).pack(anchor="w", padx=26)
        tk.Label(parent, text=subtitle, bg=BG, fg=MUTED,
                 font=(FONT, 10)).pack(anchor="w", padx=26, pady=(5, 16))

    def _panel(self, parent, title, subtitle=None):
        frame = tk.Frame(parent, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
        tk.Label(frame, text=title, bg=PANEL, fg=INK,
                 font=(FONT, 11, "bold")).pack(anchor="w", padx=16, pady=(14, 2))
        if subtitle:
            tk.Label(frame, text=subtitle, bg=PANEL, fg=MUTED,
                     font=(FONT, 9), wraplength=760, justify="left").pack(anchor="w", padx=16, pady=(0, 10))
        return frame

    def _button(self, parent, text, command, primary=False, width=None):
        b = RoundedButton(parent, text, command, primary=primary, width=width)
        b.pack(side="left", padx=(0, 8), pady=6)
        return b

    def show_home(self):
        page = self._clear("home")
        self._heading(page, "The clockwork library", "Chào mừng đến SẢNH TRUYỆN",
                      "Một góc làm việc duy nhất cho hành trình từ truyện raw đến audiobook.")
        hero = tk.Frame(page, bg="#120B0B", highlightbackground=BORDER, highlightthickness=1)
        hero.pack(fill="x", padx=26, pady=(0, 18))
        tk.Label(hero, text="✧   THƯ VIỆN CƠ KHÍ   ✧", bg="#120B0B", fg=BRASS,
                 font=(FONT, 10, "bold")).pack(anchor="w", padx=22, pady=(18, 8))
        tk.Label(hero, text="Cào. Dịch. Lắng nghe.", bg="#120B0B", fg=INK,
                 font=(FONT, 25, "bold")).pack(anchor="w", padx=22)
        tk.Label(hero, text="Giữ mọi công đoạn gọn gàng, riêng tư và lưu trực tiếp trên ổ D.",
                 bg="#120B0B", fg=MUTED, font=(FONT, 10)).pack(anchor="w", padx=22, pady=(5, 16))
        row = tk.Frame(hero, bg="#120B0B")
        row.pack(anchor="w", padx=22, pady=(0, 16))
        self._button(row, "MỞ WORKSPACE", lambda: self.navigate("scrape"), True)
        cards = tk.Frame(page, bg=BG)
        cards.pack(fill="x", padx=26)
        for col in range(3):
            cards.grid_columnconfigure(col, weight=1, uniform="card")
        card_data = [
            ("01  /  COLLECT", "Cào truyện", "Chrome thật · EPUB → TXT", "MỞ CÔNG CỤ", lambda: self.navigate("scrape")),
            ("02  /  TRANSLATE", "Dịch truyện", "Trung → Việt · chạy CPU", "MỞ BẢN DỊCH", lambda: self.navigate("translate")),
            ("03  /  LISTEN", "Tạo audio", "Nam Minh · Hoài My · MP3", "MỞ AUDIO", lambda: self.navigate("audio")),
        ]
        for col, (tag, title, desc, button, command) in enumerate(card_data):
            c = tk.Frame(cards, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
            c.grid(row=0, column=col, sticky="nsew", padx=(0 if col == 0 else 7, 7 if col < 2 else 0), pady=4)
            tk.Label(c, text=tag, bg=PANEL, fg=BRASS, font=(FONT, 8, "bold")).pack(anchor="w", padx=14, pady=(15, 10))
            tk.Label(c, text=title, bg=PANEL, fg=INK, font=(FONT, 15, "bold")).pack(anchor="w", padx=14)
            tk.Label(c, text=desc, bg=PANEL, fg=MUTED, font=(FONT, 9)).pack(anchor="w", padx=14, pady=(5, 12))
            self._button(c, button, command, primary=(col == 0), width=15).pack_configure(side="top", anchor="w", padx=14, pady=(0, 10))
        tk.Label(page, text="Gợi ý: hãy thử với một chương trước khi xử lý cả cuốn truyện.",
                 bg=BG, fg=DIM, font=(FONT, 9)).pack(anchor="w", padx=26, pady=18)

    def show_scrape(self):
        page = self._clear("scrape")
        self._heading(page, "01 / Collect", "Cào truyện", "Mở Chrome thật để dùng WebToEpub, sau đó đổi EPUB thành TXT.")
        p = self._panel(page, "BƯỚC 1 · MỞ CHROME", "WebToEpub cần được cài trong Chrome riêng. Đến trang mục lục truyện rồi bấm biểu tượng tiện ích để tạo EPUB.")
        p.pack(fill="x", padx=26, pady=(0, 12))
        bar = tk.Frame(p, bg=PANEL); bar.pack(fill="x", padx=16, pady=(0, 14))
        self._button(bar, "MỞ CHROME THẬT", self.open_chrome, True)
        self._button(bar, "MỞ THƯ MỤC EPUB", lambda: self.open_folder(EPUB_DIR))
        p2 = self._panel(page, "BƯỚC 2 · EPUB → TXT", "Chọn file EPUB đã tạo. Ứng dụng sẽ gọi epub2txt và đưa file TXT vào thư mục data/raw.")
        p2.pack(fill="x", padx=26, pady=8)
        self.epub_label = tk.Label(p2, text="Chưa chọn file EPUB", bg=PANEL, fg=MUTED, font=(FONT, 9), anchor="w")
        self.epub_label.pack(fill="x", padx=16, pady=(0, 8))
        bar2 = tk.Frame(p2, bg=PANEL); bar2.pack(fill="x", padx=16, pady=(0, 14))
        self._button(bar2, "CHỌN EPUB", self.convert_epub, True)
        self._button(bar2, "MỞ RAW TXT", lambda: self.open_folder(RAW_DIR))
        self.scrape_log = tk.Text(page, height=6, bg="#0E0A09", fg=MUTED, insertbackground=INK,
                                  font=("Consolas", 9), relief="flat", wrap="word")
        self.scrape_log.pack(fill="both", expand=True, padx=26, pady=(8, 20))
        self._log(self.scrape_log, "Sẵn sàng. EPUB không bị xóa; kết quả TXT được sao chép vào data/raw.")

    def _log(self, widget, text):
        widget.configure(state="normal")
        widget.insert("end", text.rstrip() + "\n")
        widget.see("end")
        widget.configure(state="disabled")

    def open_chrome(self):
        candidates = [
            Path(os.environ.get("PROGRAMFILES", "C:/Program Files")) / "Google/Chrome/Application/chrome.exe",
            Path(os.environ.get("PROGRAMFILES(X86)", "C:/Program Files (x86)")) / "Google/Chrome/Application/chrome.exe",
            Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/Application/chrome.exe",
        ]
        for exe in candidates:
            if exe.is_file():
                subprocess.Popen([str(exe)])
                self.status.set("Đã mở Chrome thật.")
                return
        try:
            os.startfile("chrome")  # type: ignore[attr-defined]
            return
        except Exception:
            webbrowser.open("https://www.google.com/chrome/")
            messagebox.showwarning("Chưa tìm thấy Chrome", "Không tìm thấy chrome.exe. Hãy kiểm tra Chrome đã được cài chưa.")

    def convert_epub(self):
        path = filedialog.askopenfilename(title="Chọn EPUB", initialdir=str(EPUB_DIR),
                                          filetypes=[("EPUB", "*.epub"), ("All files", "*.*")])
        if not path:
            return
        epub = Path(path)
        self.epub_label.configure(text=str(epub), fg=INK)
        if not EPUB2TXT_EXE.is_file():
            messagebox.showerror("Thiếu epub2txt", f"Không tìm thấy công cụ:\n{EPUB2TXT_EXE}\n\nHãy cài epub2txt vào môi trường đã chuẩn bị.")
            return
        self.status.set("Đang chuyển EPUB sang TXT...")
        threading.Thread(target=self._convert_worker, args=(epub,), daemon=True).start()

    def _convert_worker(self, epub: Path):
        try:
            proc = subprocess.run([str(EPUB2TXT_EXE), "-f", str(epub)], cwd=str(epub.parent),
                                  capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600)
            if proc.returncode != 0:
                raise RuntimeError((proc.stderr or proc.stdout or "epub2txt trả về lỗi").strip())
            candidates = [epub.with_suffix(".txt")]
            candidates.extend(sorted(epub.parent.glob("*.txt"), key=lambda p: p.stat().st_mtime, reverse=True))
            produced = next((p for p in candidates if p.is_file() and p.stat().st_mtime >= epub.stat().st_mtime - 2), None)
            if produced is None:
                raise RuntimeError("Lệnh hoàn tất nhưng không tìm thấy file TXT đầu ra cạnh EPUB.")
            destination = RAW_DIR / produced.name
            if produced.resolve() != destination.resolve():
                shutil.copy2(produced, destination)
            self.root.after(0, lambda: self._conversion_succeeded(destination))
        except Exception as exc:
            self.root.after(0, lambda detail=str(exc): self._conversion_failed(detail))

    def _conversion_succeeded(self, destination: Path):
        self.status.set(f"Chuyển đổi xong: {destination.name}")
        if hasattr(self, "scrape_log"):
            self._log(self.scrape_log, f"[THÀNH CÔNG] {destination}")
        messagebox.showinfo("Hoàn tất", f"Đã lưu TXT tại:\n{destination}\n\nBạn có thể mở mục Dịch truyện.")

    def _conversion_failed(self, detail: str):
        self.status.set("Chuyển EPUB thất bại.")
        if hasattr(self, "scrape_log"):
            self._log(self.scrape_log, "[LỖI] " + detail)
        messagebox.showerror("Không chuyển được EPUB", detail)

    def show_translate(self):
        page = self._clear("translate")
        self._heading(page, "02 / Translate", "Dịch truyện", "Chọn TXT tiếng Trung; mô hình HachimiMT-60 chạy CPU INT8 cục bộ.")
        tools = tk.Frame(page, bg=BG); tools.pack(fill="x", padx=26, pady=(0, 8))
        self._button(tools, "NẠP FILE RAW TXT", self.load_raw_file, True)
        self._button(tools, "MỞ THƯ MỤC BẢN DỊCH", lambda: self.open_folder(TRANSLATED_DIR))
        profile = tk.Frame(page, bg=BG); profile.pack(fill="x", padx=26, pady=(0, 10))
        tk.Label(profile, text="TỪ ĐIỂN BỘ TRUYỆN", bg=BG, fg=BRASS,
                 font=(FONT, 9, "bold")).pack(side="left", padx=(0, 10))
        if not hasattr(self, "glossary_profile_var"):
            self.glossary_profile_var = tk.StringVar(value="Lâm Thánh")
        ttk.Combobox(profile, textvariable=self.glossary_profile_var,
                     values=("Lâm Thánh", "Vớt Thi Nhân", "Từ điển chung"),
                     state="readonly", width=18, style="Dark.TCombobox").pack(side="left")
        tk.Label(profile, text="Chọn đúng truyện để giữ tên riêng và thuật ngữ nhất quán.",
                 bg=BG, fg=MUTED, font=(FONT, 9)).pack(side="left", padx=10)
        bottom = tk.Frame(page, bg=BG); bottom.pack(fill="x", padx=26, pady=10)
        panes = tk.Frame(page, bg=BG); panes.pack(fill="both", expand=True, padx=26, pady=4)
        for col in range(2):
            panes.grid_columnconfigure(col, weight=1, uniform="translation")
        panes.grid_rowconfigure(1, weight=1)
        tk.Label(panes, text="RAW / NGUYÊN BẢN", bg=BG, fg=BRASS, font=(FONT, 9, "bold")).grid(row=0, column=0, sticky="w", pady=(0, 6))
        tk.Label(panes, text="BẢN DỊCH TIẾNG VIỆT", bg=BG, fg=BRASS, font=(FONT, 9, "bold")).grid(row=0, column=1, sticky="w", padx=(10, 0), pady=(0, 6))
        self.raw_box = tk.Text(panes, bg=PANEL, fg=INK, insertbackground=INK, wrap="word", undo=True, relief="flat",
                               font=(FONT, 10), padx=12, pady=12, highlightbackground=BORDER, highlightthickness=1)
        self.vi_box = tk.Text(panes, bg=PANEL, fg=INK, insertbackground=INK, wrap="word", undo=True, relief="flat",
                              font=(FONT, 10), padx=12, pady=12, highlightbackground=BORDER, highlightthickness=1)
        self.raw_box.grid(row=1, column=0, sticky="nsew")
        self.vi_box.grid(row=1, column=1, sticky="nsew", padx=(10, 0))
        self.translate_note = tk.Label(bottom, text="Chưa nạp file.", bg=BG, fg=MUTED, font=(FONT, 9), anchor="w")
        self.translate_note.pack(side="left", fill="x", expand=True)
        self._button(bottom, "BẮT ĐẦU DỊCH", self.start_translation, True)
        self._button(bottom, "LƯU BẢN DỊCH", self.save_translation)

    def load_raw_file(self):
        path = filedialog.askopenfilename(title="Chọn raw TXT", initialdir=str(RAW_DIR),
                                          filetypes=[("Text", "*.txt"), ("All files", "*.*")])
        if not path:
            return
        try:
            text = Path(path).read_text(encoding="utf-8-sig")
        except Exception as exc:
            messagebox.showerror("Không đọc được TXT", str(exc)); return
        self.raw_path = Path(path)
        self.raw_box.delete("1.0", "end"); self.raw_box.insert("1.0", text)
        self.vi_box.delete("1.0", "end")
        self.translate_note.configure(text=f"Đã nạp: {self.raw_path.name}")
        self.status.set(f"Đã nạp raw: {self.raw_path.name}")

    def save_translation(self):
        content = self.vi_box.get("1.0", "end-1c")
        if not content.strip():
            messagebox.showwarning("Chưa có bản dịch", "Khung bản dịch đang trống."); return
        default = (self.raw_path.stem + "_vi.txt") if self.raw_path else "ban_dich_vi.txt"
        path = filedialog.asksaveasfilename(title="Lưu bản dịch", initialdir=str(TRANSLATED_DIR),
                                            initialfile=default, defaultextension=".txt",
                                            filetypes=[("Text", "*.txt")])
        if path:
            Path(path).write_text(content, encoding="utf-8")
            self.status.set(f"Đã lưu bản dịch: {Path(path).name}")

    def start_translation(self):
        if self.translation_running:
            return
        raw = self.raw_box.get("1.0", "end-1c")
        if not raw.strip():
            messagebox.showwarning("Chưa có raw", "Hãy nạp hoặc dán nội dung vào khung Raw."); return
        if not TRANSLATION_PYTHON.is_file():
            messagebox.showerror("Chưa cài bộ dịch", f"Không tìm thấy môi trường dịch:\n{TRANSLATION_PYTHON}\n\nChạy scripts\\setup_translation.ps1 trước."); return
        profile_name = self.glossary_profile_var.get()
        glossary_path = GLOSSARY_PROFILES[profile_name]
        if not glossary_path.is_file():
            messagebox.showerror("Thiếu từ điển", f"Không tìm thấy từ điển cho {profile_name}:\n{glossary_path}")
            return
        source = TEMP_DIR / "translation_input.txt"
        source.write_text(raw, encoding="utf-8")
        output = TRANSLATED_DIR / ((self.raw_path.stem if self.raw_path else "ban_dich") + "_vi.txt")
        self.translation_running = True
        self.translate_note.configure(text=f"Đang dịch bằng từ điển: {profile_name}. Lần đầu cần tải mô hình về máy.")
        self.status.set(f"Đang dịch bằng HachimiMT-60 CPU INT8 · {profile_name}...")
        threading.Thread(target=self._translation_worker, args=(source, output, glossary_path), daemon=True).start()

    def _translation_worker(self, source: Path, output: Path, glossary_path: Path):
        try:
            # Force UTF-8 in the child interpreter too: Windows legacy code pages can
            # otherwise fail when libraries print Vietnamese status/error messages.
            translation_env = os.environ.copy()
            translation_env["PYTHONUTF8"] = "1"
            translation_env["PYTHONIOENCODING"] = "utf-8:replace"
            translation_env.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
            proc = subprocess.run(
                [str(TRANSLATION_PYTHON), "-X", "utf8", str(TRANSLATION_SCRIPT), "--input", str(source),
                 "--output", str(output), "--cache-dir", str(MODEL_CACHE_DIR),
                 "--glossary", str(glossary_path)],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=None,
                cwd=str(ROOT_DIR), env=translation_env,
            )
            if proc.returncode != 0:
                raise RuntimeError((proc.stderr or proc.stdout or "Bộ dịch trả về lỗi").strip())
            translated = output.read_text(encoding="utf-8")
            self.root.after(0, lambda: self._translation_succeeded(output, translated))
        except Exception as exc:
            self.root.after(0, lambda detail=str(exc): self._translation_failed(detail))

    def _translation_succeeded(self, output: Path, translated: str):
        self.translation_running = False
        self.vi_box.delete("1.0", "end"); self.vi_box.insert("1.0", translated)
        self.translate_note.configure(text=f"Hoàn tất: {output.name}")
        self.status.set(f"Đã dịch xong: {output.name}")
        messagebox.showinfo("Dịch hoàn tất", f"Đã lưu bản dịch tại:\n{output}")

    def _translation_failed(self, detail: str):
        self.translation_running = False
        self.translate_note.configure(text="Dịch thất bại · xem thông báo lỗi")
        self.status.set("Dịch thất bại.")
        messagebox.showerror("Không dịch được", detail)

    def show_audio(self):
        page = self._clear("audio")
        self._heading(
            page, "03 / Listen", "Tạo audio",
            "Dán toàn bộ nội dung bạn muốn đọc. Mỗi lần tạo sẽ xuất đúng một file MP3 dài."
        )

        workspace = tk.Frame(page, bg=BG)
        workspace.pack(fill="both", expand=True, padx=26, pady=(0, 18))
        workspace.grid_rowconfigure(0, weight=1)
        workspace.grid_columnconfigure(0, weight=3, uniform="audio_columns")
        workspace.grid_columnconfigure(1, weight=2, uniform="audio_columns")

        left = self._panel(
            workspace, "NỘI DUNG AUDIO",
            "Dán toàn bộ bản dịch vào đây hoặc mở một file TXT dài."
        )
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8), pady=4)

        right = self._panel(
            workspace, "KẾT QUẢ AUDIO",
            "Theo dõi file đang tạo, các file đã xong và những tác vụ bị lỗi."
        )
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 0), pady=4)

        load_bar = tk.Frame(left, bg=PANEL)
        load_bar.pack(fill="x", padx=14, pady=(10, 4))
        self._button(load_bar, "MỞ FILE TXT", self.select_audio_file, True)
        self.audio_file_label = tk.Label(
            load_bar, text="Chưa nạp file · có thể dán văn bản trực tiếp",
            bg=PANEL, fg=MUTED, font=(FONT, 9), anchor="w", wraplength=330, justify="left"
        )
        self.audio_file_label.pack(side="left", fill="x", expand=True, padx=8)

        # Pack the settings and create button at the bottom so the text editor keeps
        # all remaining space even on a smaller screen.
        create_row = tk.Frame(left, bg=PANEL)
        create_row.pack(side="bottom", fill="x", padx=14, pady=(4, 12))
        # The single primary action uses GitHub Actions, which was much faster
        # than local Edge-TTS in the user's long-chapter comparison.
        self._button(
            create_row, "TẠO AUDIO", self.start_audio_generation_github,
            True, width=190
        )

        options = tk.Frame(left, bg=PANEL)
        options.pack(side="bottom", fill="x", padx=14, pady=(8, 2))
        tk.Label(options, text="GIỌNG ĐỌC", bg=PANEL, fg=BRASS,
                 font=(FONT, 8, "bold")).grid(row=0, column=0, sticky="w", padx=(0, 6), pady=4)
        if not hasattr(self, "voice_var"):
            self.voice_var = tk.StringVar(value="Nam Minh")
        ttk.Combobox(
            options, textvariable=self.voice_var, values=("Nam Minh", "Hoài My"),
            state="readonly", width=12, style="Dark.TCombobox"
        ).grid(row=0, column=1, sticky="ew", padx=(0, 14), pady=4)
        tk.Label(options, text="TỐC ĐỘ", bg=PANEL, fg=BRASS,
                 font=(FONT, 8, "bold")).grid(row=0, column=2, sticky="w", padx=(0, 6), pady=4)
        if not hasattr(self, "rate_var"):
            self.rate_var = tk.StringVar(value="1.0")
        ttk.Combobox(
            options, textvariable=self.rate_var,
            values=("0.75", "1.0", "1.25", "1.5", "1.75", "2.0"),
            state="readonly", width=7, style="Dark.TCombobox"
        ).grid(row=0, column=3, sticky="ew", pady=4)
        options.grid_columnconfigure(1, weight=1)
        options.grid_columnconfigure(3, weight=1)

        self.audio_text = tk.Text(
            left, bg="#100C0B", fg=INK, insertbackground=INK, wrap="word",
            relief="flat", font=(FONT, 10), padx=12, pady=12, undo=True,
            highlightbackground=BORDER, highlightthickness=1
        )
        self.audio_text.pack(fill="both", expand=True, padx=14, pady=(6, 4))
        self.audio_text.insert("1.0", getattr(self, "audio_draft", ""))
        self.audio_text.edit_modified(False)
        self.audio_text.bind("<<Modified>>", self._remember_audio_draft)

        result_bottom = tk.Frame(right, bg=PANEL)
        result_bottom.pack(side="bottom", fill="x", padx=14, pady=(4, 12))
        self.audio_note = tk.Label(
            result_bottom, text="Sẵn sàng · chưa có tác vụ mới",
            bg=PANEL, fg=MUTED, font=(FONT, 9), anchor="w", wraplength=310, justify="left"
        )
        self.audio_note.pack(fill="x", pady=(0, 6))
        result_buttons = tk.Frame(result_bottom, bg=PANEL)
        result_buttons.pack(fill="x")
        self._button(result_buttons, "NGHE / MỞ FILE", self.open_selected_audio_output, True)
        self._button(result_buttons, "MỞ THƯ MỤC", lambda: self.open_folder(AUDIO_DIR))

        # Live status card: spinner/check icon, current state, and elapsed time.
        self.audio_status_card = tk.Frame(
            right, bg=PANEL2, highlightbackground=BORDER, highlightthickness=1
        )
        self.audio_status_card.pack(side="bottom", fill="x", padx=14, pady=(4, 3))
        self.audio_status_icon = tk.Canvas(
            self.audio_status_card, width=34, height=34, bg=PANEL2,
            highlightthickness=0, bd=0
        )
        self.audio_status_icon.pack(side="left", padx=(10, 7), pady=7)
        status_text = tk.Frame(self.audio_status_card, bg=PANEL2)
        status_text.pack(side="left", fill="both", expand=True, pady=7)
        self.audio_status_title = tk.Label(
            status_text, text="Chưa tạo audio", bg=PANEL2, fg=MUTED,
            font=(FONT, 10, "bold"), anchor="w"
        )
        self.audio_status_title.pack(fill="x")
        self.audio_status_detail = tk.Label(
            status_text, text="Nhấn “TẠO MỘT FILE AUDIO” để bắt đầu",
            bg=PANEL2, fg=MUTED, font=(FONT, 8), anchor="w",
            wraplength=230, justify="left"
        )
        self.audio_status_detail.pack(fill="x", pady=(2, 0))
        self.audio_status_timer = tk.Label(
            self.audio_status_card, text="—", bg=PANEL2, fg=INK,
            font=(FONT, 11, "bold"), anchor="e"
        )
        self.audio_status_timer.pack(side="right", padx=(6, 12))

        self.audio_list = tk.Listbox(
            right, bg="#0E0A09", fg=INK, selectbackground="#641A23",
            relief="flat", height=10, font=(FONT, 9), activestyle="none",
            selectmode="browse"
        )
        self.audio_list.pack(fill="both", expand=True, padx=14, pady=(8, 4))
        self.audio_list_paths = {}
        self._render_audio_history()
        self._render_audio_status()

    def _remember_audio_draft(self, _event=None):
        try:
            if self.audio_text.edit_modified():
                self.audio_draft = self.audio_text.get("1.0", "end-1c")
                self.audio_text.edit_modified(False)
        except tk.TclError:
            pass

    def select_audio_file(self):
        path = filedialog.askopenfilename(
            title="Chọn một file TXT dài để tạo thành một audio",
            initialdir=str(TRANSLATED_DIR),
            filetypes=[("Text", "*.txt"), ("All files", "*.*")]
        )
        if not path:
            return
        try:
            content = Path(path).read_text(encoding="utf-8-sig")
        except Exception as exc:
            messagebox.showerror("Không đọc được TXT", str(exc))
            return
        self.audio_path = Path(path)
        self.audio_draft = content
        self.audio_text.delete("1.0", "end")
        self.audio_text.insert("1.0", content)
        self.audio_file_label.configure(text=self.audio_path.name, fg=INK)
        self.status.set(f"Đã nạp nội dung audio: {self.audio_path.name}")

    def _render_audio_history(self):
        if not hasattr(self, "audio_list"):
            return
        try:
            if not self.audio_list.winfo_exists():
                return
        except tk.TclError:
            return
        self.audio_list.delete(0, "end")
        self.audio_list_paths = {}
        for job in self.audio_history:
            state = job.get("state", "waiting")
            if state == "generating":
                engine_label = "GITHUB ACTIONS" if job.get("engine") == "github" else "MÁY"
                label = f"⏳ GENERATE · {engine_label} · {job['stem']}"
            elif state == "completed":
                path = job.get("path")
                label = f"✓ ĐÃ XONG · {Path(path).name if path else job['stem']}"
            else:
                detail = str(job.get("error") or "")
                label = f"✗ LỖI · {job['stem']}" + (f" · {detail[:70]}" if detail else "")
            self.audio_list.insert("end", label)
            index = self.audio_list.size() - 1
            if state == "completed" and job.get("path"):
                self.audio_list_paths[index] = Path(job["path"])
        if self.audio_history:
            self.audio_list.selection_clear(0, "end")
            self.audio_list.selection_set(self.audio_list.size() - 1)
            self.audio_list.see(self.audio_list.size() - 1)

    @staticmethod
    def _format_audio_elapsed(seconds: float) -> str:
        total = max(0, int(seconds))
        if total < 60:
            return f"{total}s"
        if total < 3600:
            return f"{total // 60}m {total % 60}s"
        return f"{total // 3600}h {(total % 3600) // 60}m {total % 60}s"

    def _draw_audio_status_icon(self, state: str):
        if not hasattr(self, "audio_status_icon"):
            return
        try:
            icon = self.audio_status_icon
            if not icon.winfo_exists():
                return
            icon.delete("all")
            if state == "generating":
                icon.create_arc(
                    5, 5, 29, 29, start=self._audio_spinner_angle, extent=285,
                    style="arc", outline=BRASS, width=3
                )
                self._audio_spinner_angle = (self._audio_spinner_angle + 28) % 360
            elif state == "completed":
                icon.create_line(5, 17, 12, 24, 25, 9, fill=GREEN, width=3,
                                 capstyle="round", joinstyle="round")
            elif state == "failed":
                icon.create_line(8, 8, 26, 26, fill=RED_HOVER, width=3, capstyle="round")
                icon.create_line(26, 8, 8, 26, fill=RED_HOVER, width=3, capstyle="round")
            else:
                icon.create_oval(9, 9, 25, 25, outline=BRASS, width=2)
        except tk.TclError:
            pass

    def _render_audio_status(self):
        try:
            if self.current_page != "audio" or not self.audio_status_card.winfo_exists():
                return
        except (AttributeError, tk.TclError):
            return

        job = self.audio_history[-1] if self.audio_history else None
        if job is None:
            state = "idle"
            title = "Chưa tạo audio"
            detail = "Nhấn “TẠO MỘT FILE AUDIO” để bắt đầu"
            elapsed_text = "—"
            title_color = MUTED
        else:
            state = job.get("state", "idle")
            started_at = float(job.get("started_at") or time.monotonic())
            if state == "generating":
                elapsed = time.monotonic() - started_at
                title = "generate"
                detail = str(job.get("progress") or f"Đang tạo: {job.get('stem') or 'audio'}")
                title_color = BRASS
            elif state == "completed":
                elapsed = float(job.get("duration_seconds") or 0)
                title = "completed"
                detail = f"Đã tạo xong: {Path(job.get('path') or job.get('stem') or 'audio').name}"
                title_color = GREEN
            else:
                elapsed = float(job.get("duration_seconds") or 0)
                title = "failed"
                detail = f"Tạo thất bại: {job.get('stem') or 'audio'}"
                title_color = RED_HOVER
            elapsed_text = self._format_audio_elapsed(elapsed)

        self.audio_status_title.configure(text=title, fg=title_color)
        self.audio_status_detail.configure(text=detail)
        self.audio_status_timer.configure(text=elapsed_text)
        self._draw_audio_status_icon(state)

        # A single timer drives both the live clock and the spinner animation.
        if state == "generating":
            self._schedule_audio_status_tick()

    def _schedule_audio_status_tick(self):
        if self._audio_status_after_id is not None or self.current_page != "audio":
            return
        try:
            if not self.audio_status_card.winfo_exists():
                return
            self._audio_status_after_id = self.root.after(120, self._audio_status_tick)
        except (AttributeError, tk.TclError):
            self._audio_status_after_id = None

    def _audio_status_tick(self):
        self._audio_status_after_id = None
        self._render_audio_status()

    def _finish_audio_clock(self, job: dict):
        finished_at = time.monotonic()
        started_at = float(job.get("started_at") or finished_at)
        job["finished_at"] = finished_at
        job["duration_seconds"] = max(0.0, finished_at - started_at)

    def start_audio_generation(self):
        if self.audio_running:
            messagebox.showinfo(
                "Đang tạo audio",
                "Một audio đang được tạo. Hãy chờ hoàn tất rồi tạo lượt tiếp theo để tránh gửi nhiều yêu cầu cùng lúc."
            )
            return

        text = self.audio_text.get("1.0", "end-1c").strip()
        if not text:
            messagebox.showwarning("Chưa có nội dung", "Hãy dán toàn bộ nội dung hoặc mở một file TXT trước.")
            return
        if not AUDIO_PYTHON.is_file():
            messagebox.showerror(
                "Chưa cài bộ audio",
                f"Không tìm thấy môi trường audio:\n{AUDIO_PYTHON}\n\nChạy scripts\\setup_audio.ps1 trước."
            )
            return
        if not AUDIO_TTS_GENERATOR.is_file():
            messagebox.showerror(
                "Chưa cập nhật bộ tạo audio dài",
                f"Không tìm thấy bộ tạo audio dài:\n{AUDIO_TTS_GENERATOR}\n\n"
                "Chạy scripts\\update_long_audio_tts.ps1 trước."
            )
            return

        stem = self.audio_path.stem if self.audio_path else "audio_dai"
        job_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        job = {
            "id": job_id,
            "text": text,
            "stem": stem,
            "voice": self.voice_var.get(),
            "rate": self.rate_var.get(),
            "state": "generating",
            "engine": "local",
            "path": None,
            "error": None,
            "started_at": time.monotonic(),
            "finished_at": None,
            "duration_seconds": None,
        }
        self.audio_history.append(job)
        self.audio_running = True
        self.audio_draft = text
        self.audio_note.configure(text="Đang gửi toàn bộ nội dung để tạo một file MP3 duy nhất...")
        self.status.set("Đang tạo một audio dài · vui lòng giữ ứng dụng mở.")
        self._render_audio_history()
        self._render_audio_status()
        threading.Thread(target=self._audio_worker, args=(job,), daemon=True).start()

    def start_audio_generation_github(self):
        if self.audio_running:
            messagebox.showinfo(
                "Đang tạo audio",
                "Một audio đang được tạo. Hãy chờ hoàn tất rồi tạo lượt tiếp theo."
            )
            return
        text = self.audio_text.get("1.0", "end-1c").strip()
        if not text:
            messagebox.showwarning("Chưa có nội dung", "Hãy dán nội dung hoặc mở một file TXT trước.")
            return
        if not shutil.which("gh"):
            messagebox.showerror(
                "Chưa cài GitHub CLI",
                "Để tạo audio bằng GitHub Actions, cần cài GitHub CLI rồi đăng nhập một lần.\n\n"
                "1. Mở PowerShell và chạy:\n"
                "winget install --id GitHub.cli -e\n\n"
                "2. Đóng, mở lại PowerShell rồi chạy:\n"
                "gh auth login\n\n"
                "Làm theo hướng dẫn trên màn hình và đăng nhập tài khoản GitHub của bạn."
            )
            return

        stem = self.audio_path.stem if self.audio_path else "audio_dai"
        job_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        request_id = "st-" + uuid.uuid4().hex[:16]
        job = {
            "id": job_id,
            "text": text,
            "stem": stem,
            "voice": self.voice_var.get(),
            "rate": self.rate_var.get(),
            "state": "generating",
            "engine": "github",
            "path": None,
            "error": None,
            "progress": "Đang kiểm tra đăng nhập và quyền truy cập GitHub...",
            "request_id": request_id,
            "started_at": time.monotonic(),
            "finished_at": None,
            "duration_seconds": None,
        }
        self.audio_history.append(job)
        self.audio_running = True
        self.audio_draft = text
        self.audio_note.configure(text="Đang chuẩn bị gửi chương lên GitHub Actions...")
        self.status.set("Đang tạo audio bằng GitHub Actions · vui lòng giữ ứng dụng mở.")
        self._render_audio_history()
        self._render_audio_status()
        threading.Thread(target=self._github_audio_worker, args=(job,), daemon=True).start()

    def _set_audio_job_progress(self, job_id: str, message: str):
        job = next((item for item in self.audio_history if item["id"] == job_id), None)
        if job is None:
            return
        job["progress"] = message
        if self.current_page == "audio":
            try:
                if self.audio_note.winfo_exists():
                    self.audio_note.configure(text=message)
            except tk.TclError:
                pass
            self._render_audio_status()

    def _run_github_cli(self, args: list[str], input_text: str | None = None,
                        timeout: int = 60) -> subprocess.CompletedProcess:
        executable = shutil.which("gh")
        if not executable:
            raise RuntimeError(
                "Không tìm thấy GitHub CLI (gh). Hãy cài bằng "
                "'winget install --id GitHub.cli -e', sau đó chạy 'gh auth login'."
            )
        try:
            return subprocess.run(
                [executable, *args],
                input=input_text,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                cwd=str(ROOT_DIR),
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("GitHub CLI hết thời gian chờ khi gọi API.") from exc

    def _github_audio_worker(self, job: dict):
        job_id = job["id"]
        request_id = job["request_id"]
        repo = GITHUB_AUDIO_REPO
        ref = GITHUB_AUDIO_REF
        download_dir = TEMP_DIR / f"github_audio_{job_id}"
        try:
            if repo.count("/") != 1:
                raise RuntimeError(
                    "Tên repository GitHub chưa hợp lệ. Hãy dùng dạng owner/repository."
                )

            auth = self._run_github_cli(["auth", "status", "--hostname", "github.com"])
            if auth.returncode != 0:
                detail = (auth.stderr or auth.stdout or "").strip()
                raise RuntimeError(
                    "Chưa đăng nhập GitHub CLI. Mở PowerShell, chạy 'gh auth login' "
                    "và hoàn tất hướng dẫn đăng nhập.\n" + detail[:1200]
                )

            repo_result = self._run_github_cli(["api", f"repos/{repo}"])
            if repo_result.returncode != 0:
                raise RuntimeError(
                    "Không đọc được repository GitHub. Hãy kiểm tra tài khoản đã đăng nhập "
                    "có quyền truy cập repository này.\n"
                    + (repo_result.stderr or repo_result.stdout or "")[-1600:]
                )
            try:
                repo_data = json.loads(repo_result.stdout)
            except json.JSONDecodeError as exc:
                raise RuntimeError("GitHub trả về thông tin repository không hợp lệ.") from exc
            if repo_data.get("private") is not True:
                raise RuntimeError(
                    f"Repository {repo} hiện đang Public. Vì nội dung chương được gửi lên "
                    "GitHub Actions, SẢNH TRUYỆN sẽ không gửi văn bản truyện tới repository công khai. "
                    "Hãy chuyển repository này sang Private trong GitHub Settings, hoặc cấu hình "
                    "một repository Private có workflow Generate long audio."
                )

            workflow_path = f"repos/{repo}/actions/workflows/{GITHUB_AUDIO_WORKFLOW}"
            workflow_info = self._run_github_cli(["api", workflow_path])
            if workflow_info.returncode != 0:
                raise RuntimeError(
                    "Không tìm thấy workflow Generate long audio trong repository.\n"
                    + (workflow_info.stderr or workflow_info.stdout or "")[-1600:]
                )

            packed = gzip.compress(job["text"].encode("utf-8"), compresslevel=6, mtime=0)
            encoded = base64.b64encode(packed).decode("ascii")
            if len(encoded) > GITHUB_AUDIO_MAX_ENCODED_CHARS:
                raise RuntimeError(
                    "Chương này quá lớn để gửi trực tiếp qua dữ liệu workflow_dispatch "
                    f"({len(encoded):,} ký tự sau nén; giới hạn an toàn "
                    f"{GITHUB_AUDIO_MAX_ENCODED_CHARS:,}). Không có nội dung nào được gửi. "
                    "Hãy chia chương thành phần ngắn hơn hoặc dùng quy trình tải tệp lên repository Private."
                )

            runs_endpoint = (
                f"repos/{repo}/actions/workflows/{GITHUB_AUDIO_WORKFLOW}/runs"
                f"?event=workflow_dispatch&branch={ref}&per_page=50"
            )
            before_response = self._run_github_cli(["api", runs_endpoint])
            if before_response.returncode != 0:
                raise RuntimeError(
                    "Không đọc được danh sách GitHub Actions.\n"
                    + (before_response.stderr or before_response.stdout or "")[-1200:]
                )
            try:
                before_runs = json.loads(before_response.stdout).get("workflow_runs", [])
                before_ids = {int(item["id"]) for item in before_runs}
            except (json.JSONDecodeError, TypeError, KeyError, ValueError) as exc:
                raise RuntimeError("Danh sách GitHub Actions trả về không hợp lệ.") from exc

            payload = {
                "ref": ref,
                "inputs": {
                    "content_gzip_base64": encoded,
                    "request_id": request_id,
                    "voice": job["voice"],
                    "rate": str(job["rate"]),
                },
            }
            dispatch = self._run_github_cli(
                [
                    "api", "--method", "POST",
                    f"{workflow_path}/dispatches",
                    "--input", "-",
                ],
                input_text=json.dumps(payload, ensure_ascii=False),
                timeout=90,
            )
            if dispatch.returncode != 0:
                raise RuntimeError(
                    "Không gửi được tác vụ tới GitHub Actions. Kiểm tra quyền Actions "
                    "và quyền ghi của tài khoản GitHub.\n"
                    + (dispatch.stderr or dispatch.stdout or "")[-2000:]
                )

            self.root.after(
                0, lambda j=job_id, m="Đã gửi chương lên GitHub · đang chờ runner...":
                self._set_audio_job_progress(j, m)
            )

            expected_title = f"SẢNH TRUYỆN {request_id}"
            discovery_deadline = time.monotonic() + 180
            remote_run = None
            while time.monotonic() < discovery_deadline:
                response = self._run_github_cli(["api", runs_endpoint], timeout=45)
                if response.returncode == 0:
                    try:
                        candidates = json.loads(response.stdout).get("workflow_runs", [])
                        new_candidates = [
                            item for item in candidates
                            if int(item.get("id", 0)) not in before_ids
                            and item.get("event") == "workflow_dispatch"
                        ]
                        remote_run = next(
                            (
                                item for item in new_candidates
                                if item.get("display_title") == expected_title
                            ),
                            None,
                        )
                        # Some GitHub API views may show the workflow name rather than
                        # the custom run-name. If exactly one new run exists, use it.
                        if remote_run is None and len(new_candidates) == 1:
                            remote_run = new_candidates[0]
                    except (json.JSONDecodeError, TypeError, ValueError):
                        remote_run = None
                if remote_run:
                    break
                time.sleep(5)
            if not remote_run:
                raise RuntimeError(
                    "Đã gửi lệnh nhưng không tìm thấy lượt chạy mới trong 3 phút. "
                    "Hãy mở tab Actions của repository để kiểm tra workflow có được kích hoạt không."
                )

            run_id = int(remote_run["id"])
            run_number = int(remote_run["run_number"])
            self.root.after(
                0, lambda j=job_id, m=f"GitHub Actions đang tạo audio · run #{run_number}...":
                self._set_audio_job_progress(j, m)
            )

            run_deadline = time.monotonic() + 6 * 60 * 60
            remote_status = "queued"
            while time.monotonic() < run_deadline:
                status_result = self._run_github_cli(
                    ["api", f"repos/{repo}/actions/runs/{run_id}"], timeout=45
                )
                if status_result.returncode != 0:
                    self.root.after(
                        0, lambda j=job_id, m="Đang chờ GitHub Actions phản hồi...":
                        self._set_audio_job_progress(j, m)
                    )
                    time.sleep(10)
                    continue
                try:
                    status_data = json.loads(status_result.stdout)
                except json.JSONDecodeError:
                    time.sleep(10)
                    continue
                remote_status = status_data.get("status", "queued")
                if remote_status == "completed":
                    conclusion = status_data.get("conclusion")
                    break
                self.root.after(
                    0, lambda j=job_id, m=f"GitHub Actions: {remote_status} · run #{run_number}...":
                    self._set_audio_job_progress(j, m)
                )
                time.sleep(10)
            else:
                raise RuntimeError(
                    "GitHub Actions vẫn chưa hoàn tất sau 6 giờ. Mở trang Actions để xem trạng thái run."
                )

            if conclusion != "success":
                logs = self._run_github_cli(
                    ["run", "view", str(run_id), "--repo", repo, "--log-failed"],
                    timeout=120,
                )
                log_text = (logs.stdout or "") + "\n" + (logs.stderr or "")
                log_text = log_text.strip()[-2600:]
                raise RuntimeError(
                    f"GitHub Actions kết thúc với trạng thái: {conclusion or 'không rõ'} "
                    f"(run #{run_number}).\n{log_text}"
                )

            self.root.after(
                0, lambda j=job_id, m="GitHub tạo xong · đang tải MP3 về máy...":
                self._set_audio_job_progress(j, m)
            )
            if download_dir.exists():
                shutil.rmtree(download_dir, ignore_errors=True)
            download_dir.mkdir(parents=True, exist_ok=True)
            downloaded = self._run_github_cli(
                [
                    "run", "download", str(run_id), "--repo", repo,
                    "--name", f"AU {run_number}", "--dir", str(download_dir),
                ],
                timeout=180,
            )
            if downloaded.returncode != 0:
                raise RuntimeError(
                    "GitHub đã tạo xong nhưng không tải được artifact MP3.\n"
                    + (downloaded.stderr or downloaded.stdout or "")[-1800:]
                )
            mp3_files = list(download_dir.rglob("*.mp3"))
            if not mp3_files:
                raise RuntimeError(
                    "Artifact của GitHub đã tải về nhưng không tìm thấy file MP3 bên trong."
                )

            AUDIO_DIR.mkdir(parents=True, exist_ok=True)
            safe_stem = self._safe_audio_stem(job["stem"])
            output_path = AUDIO_DIR / f"{safe_stem}_{job_id}.mp3"
            shutil.copy2(mp3_files[0], output_path)
            self.root.after(
                0, lambda j=job_id, p=output_path: self._complete_audio_job(j, p)
            )
        except Exception as exc:
            detail = str(exc).strip() or type(exc).__name__
            self.root.after(
                0, lambda j=job_id, d=detail: self._fail_audio_job(j, d)
            )
        finally:
            if download_dir.exists():
                shutil.rmtree(download_dir, ignore_errors=True)

    @staticmethod
    def _safe_audio_stem(stem: str) -> str:
        # Remove Windows-invalid filename characters while preserving Vietnamese.
        invalid = set('<>:"/\\\\|?*')
        clean = "".join("_" if char in invalid or ord(char) < 32 else char for char in stem)
        return clean.strip(" .") or "audio"

    def _audio_worker(self, job: dict):
        job_id = job["id"]
        input_path = TEMP_DIR / f"long_tts_input_{job_id}.txt"
        safe_stem = self._safe_audio_stem(job["stem"])
        output_path = AUDIO_DIR / f"{safe_stem}_{job_id}.mp3"
        voice_ids = {
            "Nam Minh": "vi-VN-NamMinhNeural",
            "Hoài My": "vi-VN-HoaiMyNeural",
        }
        try:
            input_path.write_text(job["text"], encoding="utf-8")
            AUDIO_DIR.mkdir(parents=True, exist_ok=True)
            # Long chapters can take many minutes per full-text request. Do not
            # repeat the entire long request three times when the provider returns
            # no audio; stop after one attempt so the diagnostic log is available.
            attempts = "1" if len(job["text"]) >= 5000 else "3"
            proc = subprocess.run(
                [
                    str(AUDIO_PYTHON), str(AUDIO_TTS_GENERATOR),
                    "--input", str(input_path), "--output", str(output_path),
                    "--voice", voice_ids[job["voice"]], "--rate", job["rate"], "--attempts", attempts,
                ],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=None, cwd=str(ROOT_DIR),
            )
            if proc.returncode != 0:
                raise RuntimeError((proc.stderr or proc.stdout or "Bộ tạo audio dài trả về lỗi.").strip())
            if not output_path.is_file() or output_path.stat().st_size < 128:
                raise RuntimeError("File MP3 đầu ra rỗng hoặc không hợp lệ.")
            self.root.after(0, lambda j=job_id, p=output_path: self._complete_audio_job(j, p))
        except Exception as exc:
            detail = str(exc).strip() or type(exc).__name__
            self.root.after(0, lambda j=job_id, d=detail: self._fail_audio_job(j, d))
        finally:
            input_path.unlink(missing_ok=True)

    def _complete_audio_job(self, job_id: str, path: Path):
        job = next((item for item in self.audio_history if item["id"] == job_id), None)
        if job is None:
            return
        job["state"] = "completed"
        job["path"] = str(path)
        job["error"] = None
        self._finish_audio_clock(job)
        self.audio_running = False
        self.audio_outputs.append(path)
        self.status.set(f"Audio hoàn tất: {path.name}")
        self._render_audio_status()
        if self.current_page == "audio":
            try:
                if self.audio_note.winfo_exists():
                    self.audio_note.configure(text=f"Đã tạo xong một file audio duy nhất: {path.name}")
                    self._render_audio_history()
                    messagebox.showinfo("Tạo audio thành công", f"Đã tạo một file MP3 hoàn chỉnh:\n{path}")
            except tk.TclError:
                pass

    def _fail_audio_job(self, job_id: str, detail: str):
        job = next((item for item in self.audio_history if item["id"] == job_id), None)
        if job is None:
            return
        job["state"] = "failed"
        job["error"] = detail
        self._finish_audio_clock(job)
        self.audio_running = False
        self.status.set("Tạo audio thất bại.")
        self._render_audio_status()
        if self.current_page == "audio":
            try:
                if self.audio_note.winfo_exists():
                    self.audio_note.configure(text="Tạo audio thất bại · xem chi tiết ở khung kết quả.")
                    self._render_audio_history()
                    messagebox.showerror("Không tạo được audio", detail[:3000])
            except tk.TclError:
                pass

    def open_selected_audio_output(self):
        try:
            index = self.audio_list.curselection()[0]
        except Exception:
            messagebox.showinfo("Chọn kết quả", "Hãy chọn một file audio đã tạo xong ở khung bên phải.")
            return
        path = self.audio_list_paths.get(index)
        if path and path.is_file():
            try:
                os.startfile(str(path))  # type: ignore[attr-defined]
            except Exception:
                webbrowser.open(path.as_uri())
        else:
            messagebox.showinfo(
                "Audio chưa sẵn sàng",
                "Dòng đang chọn chưa có MP3 hoàn chỉnh. Hãy chọn dòng bắt đầu bằng “✓ ĐÃ XONG”."
            )

    def open_folder(self, folder: Path):
        folder.mkdir(parents=True, exist_ok=True)
        try:
            os.startfile(str(folder))  # type: ignore[attr-defined]
        except Exception:
            messagebox.showinfo("Thư mục", str(folder))

def main():
    root = tk.Tk()
    app = NovelStudioApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
