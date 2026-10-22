from __future__ import annotations

import os
import shutil
import subprocess
import threading
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
            proc = subprocess.run(
                [str(TRANSLATION_PYTHON), str(TRANSLATION_SCRIPT), "--input", str(source),
                 "--output", str(output), "--cache-dir", str(MODEL_CACHE_DIR),
                 "--glossary", str(glossary_path)],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=None,
                cwd=str(ROOT_DIR),
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
        self._heading(page, "03 / Listen", "Tạo audio", "Chọn nhiều chương TXT; Vietnamese-Long-Audio-TTS tạo một MP3 hoàn chỉnh cho từng chương. Cần Internet.")
        control = self._panel(page, "NỘI DUNG VÀ THIẾT LẬP", "Nên bắt đầu với một chương. Văn bản dài sẽ được chia thành nhiều phần để giảm lỗi dịch vụ.")
        control.pack(fill="x", padx=26, pady=(0, 10))
        bar = tk.Frame(control, bg=PANEL); bar.pack(fill="x", padx=16, pady=(0, 10))
        self._button(bar, "CHỌN NHIỀU CHƯƠNG TXT", self.select_audio_file, True)
        self.audio_file_label = tk.Label(bar, text="Chưa chọn file", bg=PANEL, fg=MUTED, font=(FONT, 9), anchor="w")
        self.audio_file_label.pack(side="left", fill="x", expand=True, padx=8)
        opts = tk.Frame(control, bg=PANEL); opts.pack(fill="x", padx=16, pady=(0, 12))
        tk.Label(opts, text="GIỌNG", bg=PANEL, fg=BRASS, font=(FONT, 8, "bold")).pack(side="left", padx=(0, 7))
        self.voice_var = tk.StringVar(value="Nam Minh")
        ttk.Combobox(opts, textvariable=self.voice_var, values=("Nam Minh", "Hoài My"),
                     state="readonly", width=14, style="Dark.TCombobox").pack(side="left", padx=(0, 18))
        tk.Label(opts, text="TỐC ĐỘ", bg=PANEL, fg=BRASS, font=(FONT, 8, "bold")).pack(side="left", padx=(0, 7))
        self.rate_var = tk.StringVar(value="1.0")
        ttk.Combobox(opts, textvariable=self.rate_var, values=("0.75", "1.0", "1.25", "1.5", "1.75", "2.0"),
                     state="readonly", width=10, style="Dark.TCombobox").pack(side="left")

        # Pin the actions at the bottom of the window before packing expandable widgets.
        # This prevents the generate buttons from being pushed below the visible area.
        bottom = tk.Frame(page, bg=BG)
        bottom.pack(side="bottom", fill="x", padx=26, pady=10)
        self.audio_note = tk.Label(bottom, text="Chưa có tác vụ.", bg=BG, fg=MUTED, font=(FONT, 9), anchor="w")
        self.audio_note.pack(side="left", fill="x", expand=True)
        self._button(bottom, "THÊM VÀO HÀNG ĐỢI", self.add_audio_to_queue, True)
        self._button(bottom, "BẮT ĐẦU TẠO AUDIO", self.start_audio_generation, True)
        self._button(bottom, "NGHE / MỞ KẾT QUẢ", self.open_selected_audio_output)

        self.audio_text = tk.Text(page, height=5, bg=PANEL, fg=INK, insertbackground=INK, wrap="word",
                                  relief="flat", font=(FONT, 10), padx=12, pady=12,
                                  highlightbackground=BORDER, highlightthickness=1)
        self.audio_text.pack(fill="x", expand=False, padx=26, pady=(0, 10))
        queue_panel = self._panel(page, "HÀNG ĐỢI AUDIO", "Có thể chọn 15 file TXT cùng lúc; mỗi file sẽ thành một MP3 riêng. Chọn kết quả hoàn chỉnh để nghe hoặc mở file.")
        queue_panel.pack(fill="both", expand=True, padx=26, pady=(0, 8))
        self.audio_list = tk.Listbox(queue_panel, bg="#0E0A09", fg=INK, selectbackground="#641A23",
                                     relief="flat", height=4, font=(FONT, 9), activestyle="none")
        self.audio_list.pack(fill="both", expand=True, padx=16, pady=(5, 12))
        self.audio_list_paths: dict[int, Path] = {}

    def select_audio_file(self):
        paths = filedialog.askopenfilenames(
            title="Chọn một hoặc nhiều chương TXT tiếng Việt",
            initialdir=str(TRANSLATED_DIR),
            filetypes=[("Text", "*.txt"), ("All files", "*.*")]
        )
        if not paths:
            return
        self.audio_paths = [Path(p) for p in paths]
        self.audio_path = self.audio_paths[0] if len(self.audio_paths) == 1 else None
        try:
            preview = self.audio_paths[0].read_text(encoding="utf-8-sig")
        except Exception as exc:
            messagebox.showerror("Không đọc được TXT", str(exc))
            return
        self.audio_text.delete("1.0", "end")
        self.audio_text.insert("1.0", preview)
        if len(self.audio_paths) == 1:
            label = self.audio_paths[0].name
            self.status.set(f"Đã nạp file audio: {label}")
        else:
            label = f"Đã chọn {len(self.audio_paths)} chương TXT · mỗi chương thành một MP3 riêng"
            self.status.set(f"Đã chọn {len(self.audio_paths)} chương để tạo audio hàng loạt.")
        self.audio_file_label.configure(text=label, fg=INK)

    def add_audio_to_queue(self):
        voice = self.voice_var.get()
        rate = self.rate_var.get()
        added = 0
        skipped: list[str] = []

        def enqueue(text: str, stem: str):
            nonlocal added
            if not text.strip():
                skipped.append(f"{stem}: file trống")
                return
            created = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            job = {"text": text, "stem": stem, "voice": voice, "rate": rate, "created": created}
            self.audio_queue.append(job)
            number = len(self.audio_queue)
            self.audio_list.insert("end", f"AU {number} · {stem} · {voice} · {rate}× · Chờ")
            added += 1

        # Multiple selected files are queued as separate chapters, not concatenated.
        if len(self.audio_paths) > 1:
            for path in self.audio_paths:
                try:
                    enqueue(path.read_text(encoding="utf-8-sig"), path.stem)
                except Exception as exc:
                    skipped.append(f"{path.name}: {exc}")
        else:
            text = self.audio_text.get("1.0", "end-1c").strip()
            if not text:
                messagebox.showwarning("Chưa có nội dung", "Hãy chọn file TXT hoặc dán văn bản trước.")
                return
            stem = self.audio_path.stem if self.audio_path else "noi_dung"
            enqueue(text, stem)

        if added:
            self.audio_note.configure(text=f"Đã thêm {added} chương/tác vụ vào hàng đợi.")
            self.status.set(f"Đã thêm {added} tác vụ audio.")
            # Consume the current selection so pressing Start again cannot silently
            # queue the same batch a second time after it has completed.
            self.audio_paths = []
            self.audio_path = None
            self.audio_text.delete("1.0", "end")
            self.audio_file_label.configure(text=f"Đã thêm {added} chương vào hàng đợi", fg=INK)
        if skipped:
            messagebox.showwarning("Một số file bị bỏ qua", "\n".join(skipped[:8]))
        if not added and skipped:
            self.audio_note.configure(text="Không có file hợp lệ để tạo audio.")

    @staticmethod
    def _split_audio_text(text: str, limit: int = 1800) -> list[str]:
        """Split text conservatively, preserving all non-whitespace content."""
        import re
        normalized = text.strip()
        if not normalized:
            return []
        pieces = re.split(r"(?<=[。！？!?；;.!?])\s+|\n+", normalized)
        chunks: list[str] = []
        current = ""
        for piece in pieces:
            piece = piece.strip()
            if not piece:
                continue
            while len(piece) > limit:
                cut = piece.rfind(" ", 0, limit + 1)
                if cut < max(1, limit // 2):
                    cut = limit
                prefix, piece = piece[:cut].strip(), piece[cut:].strip()
                if prefix:
                    if current:
                        chunks.append(current)
                        current = ""
                    chunks.append(prefix)
            if current and len(current) + 1 + len(piece) > limit:
                chunks.append(current)
                current = piece
            else:
                current = (current + " " + piece).strip()
        if current:
            chunks.append(current)
        # Fallback when regex has normalized separators and would lose line breaks only.
        return chunks

    def start_audio_generation(self):
        if self.audio_running:
            return
        if not self.audio_queue:
            self.add_audio_to_queue()
            if not self.audio_queue:
                return
        if not AUDIO_PYTHON.is_file():
            messagebox.showerror("Chưa cài bộ audio", f"Không tìm thấy môi trường audio:\n{AUDIO_PYTHON}\n\nChạy scripts\\setup_audio.ps1 trước.")
            return
        if not AUDIO_TTS_GENERATOR.is_file():
            messagebox.showerror(
                "Chưa cập nhật bộ tạo audio dài",
                f"Không tìm thấy bộ tạo audio của Vietnamese-Long-Audio-TTS:\n{AUDIO_TTS_GENERATOR}\n\n"
                "Hãy chạy scripts\\update_long_audio_tts.ps1 trước."
            )
            return
        pending = list(self.audio_queue)
        self.audio_queue.clear()
        self.audio_running = True
        self.audio_note.configure(text=f"Đang tạo {len(pending)} file MP3 hoàn chỉnh...")
        threading.Thread(target=self._audio_worker, args=(pending,), daemon=True).start()

    @staticmethod
    def _safe_audio_stem(stem: str) -> str:
        import re
        return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", stem).strip(" .") or "audio"

    def _append_audio_result(self, path: Path):
        self.audio_list.insert("end", f"✓ MP3 hoàn chỉnh · {path.name}")
        self.audio_list_paths[self.audio_list.size() - 1] = path

    def _audio_worker(self, pending: list[dict]):
        failed: list[str] = []
        voice_ids = {
            "Nam Minh": "vi-VN-NamMinhNeural",
            "Hoài My": "vi-VN-HoaiMyNeural",
        }
        for job_no, job in enumerate(pending, 1):
            safe_stem = self._safe_audio_stem(job["stem"])
            # One TXT chapter creates one completed MP3 in the audio folder.
            final_path = AUDIO_DIR / f"{safe_stem}_{job['created']}_{job_no:02d}.mp3"
            input_path = TEMP_DIR / f"long_tts_input_{job['created']}_{job_no:02d}.txt"
            input_path.write_text(job["text"], encoding="utf-8")
            self.root.after(0, lambda j=job_no, n=len(pending): self.audio_note.configure(
                text=f"Đang tạo MP3 hoàn chỉnh · chương {j}/{n}"))
            try:
                proc = subprocess.run(
                    [str(AUDIO_PYTHON), str(AUDIO_TTS_GENERATOR),
                     "--input", str(input_path), "--output", str(final_path),
                     "--voice", voice_ids[job["voice"]], "--rate", job["rate"], "--attempts", "3"],
                    capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=None,
                    cwd=str(ROOT_DIR),
                )
                if proc.returncode != 0:
                    raise RuntimeError((proc.stderr or proc.stdout or "Vietnamese-Long-Audio-TTS trả về lỗi.").strip())
                if not final_path.is_file() or final_path.stat().st_size < 128:
                    raise RuntimeError("File MP3 đầu ra rỗng hoặc không hợp lệ.")
                self.audio_outputs.append(final_path)
                self.root.after(0, lambda path=final_path: self._append_audio_result(path))
            except Exception as exc:
                failed.append(f"{job['stem']}: {exc}")
                self.root.after(0, lambda stem=job["stem"], d=str(exc): self.audio_list.insert(
                    "end", f"✗ {stem}: {d[:160]}"))
            finally:
                input_path.unlink(missing_ok=True)
        self.root.after(0, lambda: self._audio_generation_finished(failed))

    def _audio_generation_finished(self, failed: list[str]):
        self.audio_running = False
        if failed:
            self.audio_note.configure(text=f"Chưa hoàn tất · {len(failed)} chương audio bị lỗi")
            self.status.set("Audio hoàn thành một phần; xem chi tiết trong hàng đợi.")
            messagebox.showwarning("Một số chương audio thất bại", "\n\n".join(failed[:4]))
        else:
            self.audio_note.configure(text="Hoàn thành · Có thể chọn file MP3 để nghe.")
            self.status.set("Tạo audio hoàn tất.")
            messagebox.showinfo("Audio hoàn tất", "Đã tạo xong một file MP3 hoàn chỉnh cho mỗi chương thành công. Chọn file rồi bấm NGHE / MỞ KẾT QUẢ.")

    def open_selected_audio_output(self):
        try:
            index = self.audio_list.curselection()[0]
        except Exception:
            messagebox.showinfo("Chọn kết quả", "Hãy chọn một dòng MP3 hoàn chỉnh trong hàng đợi trước.")
            return
        path = self.audio_list_paths.get(index)
        if path and path.is_file():
            try:
                os.startfile(str(path))  # type: ignore[attr-defined]
            except Exception:
                webbrowser.open(path.as_uri())
        else:
            messagebox.showinfo("Chưa phải file hoàn chỉnh",
                                "Chọn dòng có dấu ✓ MP3 hoàn chỉnh để nghe hoặc mở file.")
            self.open_folder(AUDIO_DIR)

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
