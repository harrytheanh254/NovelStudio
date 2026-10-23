from __future__ import annotations

import argparse
import html
from html.parser import HTMLParser
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path


PLAIN_TEXT_EXTENSIONS = {
    ".txt", ".md", ".markdown", ".rst", ".log", ".csv", ".json", ".jsonl",
    ".yaml", ".yml", ".toml", ".ini", ".conf", ".cfg", ".tsv",
}
HTML_EXTENSIONS = {".html", ".htm", ".xhtml"}
ARCHIVE_DOCUMENT_EXTENSIONS = {".docx", ".odt", ".fb2"}
SUPPORTED_DOCUMENT_EXTENSIONS = (
    PLAIN_TEXT_EXTENSIONS
    | HTML_EXTENSIONS
    | ARCHIVE_DOCUMENT_EXTENSIONS
    | {".epub", ".rtf", ".pdf", ".mobi", ".azw", ".azw3", ".doc"}
)


def decode_bytes(data: bytes) -> str:
    """Decode common Windows, UTF-8 and Chinese text encodings without dropping bytes."""
    for encoding in ("utf-8-sig", "utf-16", "utf-32", "gb18030", "cp1252"):
        try:
            return data.decode(encoding)
        except (UnicodeDecodeError, UnicodeError):
            continue
    return data.decode("utf-8", errors="replace")


def normalize_extracted_text(text: str) -> str:
    """Normalize only layout whitespace from formats that contain markup."""
    lines = [re.sub(r"[ \t\u00a0]+", " ", line).strip() for line in text.splitlines()]
    result = "\n".join(lines)
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result.strip()


class _HTMLTextExtractor(HTMLParser):
    BLOCK_TAGS = {
        "address", "article", "aside", "blockquote", "br", "dd", "div", "dl",
        "dt", "figcaption", "figure", "footer", "h1", "h2", "h3", "h4", "h5",
        "h6", "header", "hr", "li", "main", "ol", "p", "pre", "section", "tr",
        "td", "th", "ul",
    }
    IGNORED_TAGS = {"head", "script", "style", "noscript", "svg", "template"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.suppressed: list[str] = []

    def handle_starttag(self, tag: str, attrs):
        tag = tag.lower()
        if self.suppressed:
            if tag not in {"br", "img", "meta", "link", "hr", "input"}:
                self.suppressed.append(tag)
            return
        if tag in self.IGNORED_TAGS:
            self.suppressed.append(tag)
            return
        if tag in self.BLOCK_TAGS:
            self.parts.append("\n")

    def handle_startendtag(self, tag: str, attrs):
        tag = tag.lower()
        if not self.suppressed and tag in self.BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str):
        tag = tag.lower()
        if self.suppressed:
            for index in range(len(self.suppressed) - 1, -1, -1):
                if self.suppressed[index] == tag:
                    del self.suppressed[index:]
                    break
            return
        if tag in self.BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str):
        if not self.suppressed and data:
            self.parts.append(data)

    def text(self) -> str:
        return normalize_extracted_text(html.unescape("".join(self.parts)))


def html_to_text(data: bytes) -> str:
    parser = _HTMLTextExtractor()
    parser.feed(decode_bytes(data))
    parser.close()
    return parser.text()


def rtf_to_text(data: bytes) -> str:
    """Best-effort extraction of ordinary RTF text; complex layout may be simplified."""
    source = decode_bytes(data)
    # Remove RTF destinations commonly used for metadata and embedded objects.
    source = re.sub(
        r"\{\\(?:fonttbl|colortbl|stylesheet|info|pict|object|header\\w*|footer\\w*)\b.*?\}",
        "",
        source,
        flags=re.IGNORECASE | re.DOTALL,
    )

    def hex_char(match: re.Match) -> str:
        return bytes([int(match.group(1), 16)]).decode("cp1252", errors="replace")

    source = re.sub(r"\\'[0-9a-fA-F]{2}", hex_char, source)

    def unicode_char(match: re.Match) -> str:
        value = int(match.group(1))
        if value < 0:
            value += 65536
        try:
            return chr(value)
        except ValueError:
            return "\ufffd"

    source = re.sub(r"\\u(-?\d+)\??", unicode_char, source)
    source = re.sub(r"\\(?:par|line|page|row)\b\s?", "\n", source, flags=re.IGNORECASE)
    source = re.sub(r"\\tab\b\s?", "\t", source, flags=re.IGNORECASE)
    source = re.sub(r"\\[a-zA-Z]+-?\d*\s?", "", source)
    source = re.sub(r"\\([{}\\])", r"\1", source)
    source = source.replace("{", "").replace("}", "")
    return normalize_extracted_text(source)


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def _element_text(node: ET.Element) -> str:
    parts: list[str] = []

    def walk(item: ET.Element):
        for child in item:
            name = _local_name(child.tag)
            if name in {"tab", "tab-stop"}:
                parts.append("\t")
            elif name in {"line-break", "br"}:
                parts.append("\n")
            else:
                if child.text:
                    parts.append(child.text)
                walk(child)
            if child.tail:
                parts.append(child.tail)

    if node.text:
        parts.append(node.text)
    walk(node)
    return "".join(parts).strip()


def docx_to_text(path: Path) -> str:
    try:
        with zipfile.ZipFile(path) as archive:
            xml_data = archive.read("word/document.xml")
    except (zipfile.BadZipFile, KeyError) as exc:
        raise ValueError("Tệp DOCX không hợp lệ hoặc thiếu phần nội dung chính.") from exc
    try:
        root = ET.fromstring(xml_data)
    except ET.ParseError as exc:
        raise ValueError("Không đọc được cấu trúc DOCX.") from exc

    paragraphs: list[str] = []
    for paragraph in root.iter():
        if _local_name(paragraph.tag) != "p":
            continue
        pieces: list[str] = []
        for node in paragraph.iter():
            name = _local_name(node.tag)
            if name == "t" and node.text:
                pieces.append(node.text)
            elif name in {"tab", "ptab"}:
                pieces.append("\t")
            elif name in {"br", "cr"}:
                pieces.append("\n")
        value = "".join(pieces).strip()
        if value:
            paragraphs.append(value)
    return "\n\n".join(paragraphs)


def odt_to_text(path: Path) -> str:
    try:
        with zipfile.ZipFile(path) as archive:
            xml_data = archive.read("content.xml")
    except (zipfile.BadZipFile, KeyError) as exc:
        raise ValueError("Tệp ODT không hợp lệ hoặc thiếu content.xml.") from exc
    try:
        root = ET.fromstring(xml_data)
    except ET.ParseError as exc:
        raise ValueError("Không đọc được cấu trúc ODT.") from exc

    paragraphs = []
    for node in root.iter():
        if _local_name(node.tag) in {"p", "h"}:
            value = _element_text(node)
            if value:
                paragraphs.append(value)
    return "\n\n".join(paragraphs)


def fb2_to_text(path: Path) -> str:
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError) as exc:
        raise ValueError("Tệp FB2 không hợp lệ hoặc không đọc được.") from exc

    paragraphs = []
    for node in root.iter():
        if _local_name(node.tag) in {"book-title", "subtitle", "text-author", "p", "v", "date"}:
            value = _element_text(node)
            if value:
                paragraphs.append(value)
    return "\n\n".join(paragraphs)


def find_executable(name: str, candidates: tuple[Path, ...] = ()) -> str | None:
    located = shutil.which(name)
    if located:
        return located
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    return None


def calibre_to_text(source: Path, output: Path) -> None:
    candidates = (
        Path("C:/Program Files/Calibre2/ebook-convert.exe"),
        Path("C:/Program Files/Calibre/ebook-convert.exe"),
        Path.home() / "AppData/Local/Programs/calibre/ebook-convert.exe",
    )
    executable = find_executable("ebook-convert", candidates)
    if not executable:
        raise RuntimeError(
            f"Định dạng {source.suffix.upper()} cần Calibre (ebook-convert). "
            "Hãy cài Calibre hoặc chọn một định dạng được hỗ trợ trực tiếp."
        )
    proc = subprocess.run(
        [executable, str(source), str(output), "--txt-output-formatting", "plain"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900,
    )
    if proc.returncode != 0 or not output.is_file():
        detail = (proc.stderr or proc.stdout or "Calibre không tạo được TXT.").strip()
        raise RuntimeError(detail)


def legacy_doc_to_text(source: Path, output: Path) -> None:
    candidates = (
        Path("C:/Program Files/LibreOffice/program/soffice.exe"),
        Path("C:/Program Files (x86)/LibreOffice/program/soffice.exe"),
    )
    executable = find_executable("soffice", candidates)
    if not executable:
        raise RuntimeError(
            "Định dạng DOC cũ cần LibreOffice. Có thể lưu tài liệu thành DOCX hoặc RTF rồi thử lại."
        )
    with tempfile.TemporaryDirectory(prefix="sanhtruyen_doc_") as temp_dir:
        proc = subprocess.run(
            [executable, "--headless", "--convert-to", "txt:Text", "--outdir", temp_dir, str(source)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900,
        )
        generated = Path(temp_dir) / f"{source.stem}.txt"
        if proc.returncode != 0 or not generated.is_file():
            detail = (proc.stderr or proc.stdout or "LibreOffice không tạo được TXT.").strip()
            raise RuntimeError(detail)
        text = decode_bytes(generated.read_bytes())
        output.write_text(text, encoding="utf-8", newline="")


def pdf_to_text(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError(
            "Để đọc PDF, cần cài pypdf vào môi trường dịch của SẢNH TRUYỆN. "
            "Hãy chạy: envs\\translation\\Scripts\\python.exe -m pip install pypdf"
        ) from exc

    try:
        reader = PdfReader(str(path), strict=False)
        if reader.is_encrypted:
            try:
                reader.decrypt("")
            except Exception as exc:
                raise RuntimeError("PDF được mã hóa bằng mật khẩu nên không thể đọc trực tiếp.") from exc
        pages = []
        for index, page in enumerate(reader.pages):
            value = (page.extract_text() or "").strip()
            if value:
                pages.append(value)
        text = "\n\n".join(pages).strip()
    except Exception as exc:
        if isinstance(exc, RuntimeError):
            raise
        raise RuntimeError(f"Không thể trích xuất văn bản từ PDF: {exc}") from exc

    if not text:
        raise RuntimeError(
            "PDF không có lớp văn bản đọc được (có thể là bản scan dạng ảnh). "
            "Ứng dụng chưa bật OCR, nên không tạo file TXT rỗng."
        )
    return text


def convert_document_to_text(source: Path) -> str:
    """Convert supported non-EPUB documents to plain text without changing the source."""
    source = Path(source)
    if not source.is_file():
        raise FileNotFoundError(f"Không tìm thấy tệp: {source}")
    extension = source.suffix.lower()

    if extension == ".epub":
        raise ValueError("EPUB được chuyển bằng công cụ epub2txt tích hợp trong SẢNH TRUYỆN.")
    if extension in PLAIN_TEXT_EXTENSIONS:
        text = decode_bytes(source.read_bytes())
    elif extension in HTML_EXTENSIONS:
        text = html_to_text(source.read_bytes())
    elif extension == ".rtf":
        text = rtf_to_text(source.read_bytes())
    elif extension == ".docx":
        text = docx_to_text(source)
    elif extension == ".odt":
        text = odt_to_text(source)
    elif extension == ".fb2":
        text = fb2_to_text(source)
    elif extension == ".pdf":
        text = pdf_to_text(source)
    elif extension in {".mobi", ".azw", ".azw3"}:
        raise ValueError(
            "Định dạng sách Kindle này cần Calibre. Gọi calibre_to_text(source, output) "
            "từ luồng chuyển đổi của ứng dụng."
        )
    elif extension == ".doc":
        raise ValueError(
            "Định dạng DOC cũ cần LibreOffice. Gọi legacy_doc_to_text(source, output) "
            "từ luồng chuyển đổi của ứng dụng."
        )
    else:
        supported = ", ".join(sorted(SUPPORTED_DOCUMENT_EXTENSIONS))
        raise ValueError(f"Chưa hỗ trợ định dạng {extension or '(không có phần mở rộng)'}. Hỗ trợ: {supported}")

    if not text.strip():
        raise ValueError("Không trích xuất được văn bản có nội dung từ tệp này.")
    return text


def main() -> int:
    parser = argparse.ArgumentParser(description="SẢNH TRUYỆN: chuyển tài liệu phổ biến thành TXT.")
    parser.add_argument("--input", required=True, type=Path, help="Tệp nguồn.")
    parser.add_argument("--output", required=True, type=Path, help="Đường dẫn TXT đầu ra.")
    args = parser.parse_args()
    try:
        extension = args.input.suffix.lower()
        if extension in {".mobi", ".azw", ".azw3"}:
            calibre_to_text(args.input, args.output)
        elif extension == ".doc":
            legacy_doc_to_text(args.input, args.output)
        else:
            text = convert_document_to_text(args.input)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(text, encoding="utf-8", newline="")
        if not args.output.is_file() or not args.output.read_text(encoding="utf-8").strip():
            raise RuntimeError("Đã chạy chuyển đổi nhưng kết quả TXT rỗng.")
        print(f"[SUCCESS] Đã chuyển {args.input.name} thành {args.output.name}.", flush=True)
        return 0
    except Exception as exc:
        try:
            args.output.unlink(missing_ok=True)
        except OSError:
            pass
        print(f"[ERROR] {exc}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
