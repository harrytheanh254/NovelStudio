import importlib.util
import tempfile
import unittest
import zipfile
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "document_to_text.py"
SPEC = importlib.util.spec_from_file_location("document_to_text_tests", MODULE_PATH)
CONVERTER = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(CONVERTER)


class DocumentToTextTests(unittest.TestCase):
    def test_plain_text_preserves_chinese_and_paragraphs(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "novel.md"
            expected = "第一章，天崩開局\n\n「咳咳！」\n\n正文。"
            source.write_text(expected, encoding="utf-8")
            self.assertEqual(CONVERTER.convert_document_to_text(source), expected)

    def test_html_extracts_paragraphs_and_skips_script_and_style(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "novel.html"
            source.write_text(
                "<html><head><style>.x{color:red}</style><title>ignored</title></head>"
                "<body><h1>第一章</h1><p>正文 <b>内容</b></p>"
                "<script>bad_script()</script><p>下一段</p></body></html>",
                encoding="utf-8",
            )
            result = CONVERTER.convert_document_to_text(source)
            self.assertIn("第一章", result)
            self.assertIn("正文 内容", result)
            self.assertIn("下一段", result)
            self.assertNotIn("bad_script", result)
            self.assertNotIn("color:red", result)
            self.assertNotIn("ignored", result)

    def test_rtf_removes_formatting_controls_and_keeps_text(self):
        text = CONVERTER.rtf_to_text(
            r"{\rtf1\ansi \b 第一章\b0\par 正文内容}".encode("utf-8")
        )
        self.assertIn("第一章", text)
        self.assertIn("正文内容", text)
        self.assertNotIn("rtf1", text)
        self.assertNotIn("ansi", text)

    def test_docx_extracts_paragraph_text(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "novel.docx"
            document = (
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                '<w:body><w:p><w:r><w:t>第一章，天崩開局</w:t></w:r></w:p>'
                '<w:p><w:r><w:t>正文内容。</w:t></w:r></w:p></w:body></w:document>'
            )
            with zipfile.ZipFile(source, "w") as archive:
                archive.writestr("word/document.xml", document)
            result = CONVERTER.convert_document_to_text(source)
            self.assertEqual(result, "第一章，天崩開局\n\n正文内容。")

    def test_odt_extracts_paragraphs_with_namespaces(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "novel.odt"
            document = (
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<office:document-content '
                'xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
                'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0">'
                '<office:body><office:text><text:p>第一段</text:p>'
                '<text:p>第二段<text:span>补充</text:span></text:p>'
                '</office:text></office:body></office:document-content>'
            )
            with zipfile.ZipFile(source, "w") as archive:
                archive.writestr("content.xml", document)
            result = CONVERTER.convert_document_to_text(source)
            self.assertEqual(result, "第一段\n\n第二段补充")

    def test_xml_extracts_leaf_text_without_markup(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "novel.xml"
            source.write_text(
                "<book><chapter><title>第一章</title><p>正文内容。</p></chapter></book>",
                encoding="utf-8",
            )
            result = CONVERTER.convert_document_to_text(source)
            self.assertIn("第一章", result)
            self.assertIn("正文内容。", result)
            self.assertNotIn("<chapter>", result)

    def test_empty_and_unsupported_inputs_are_reported(self):
        with tempfile.TemporaryDirectory() as folder:
            empty = Path(folder) / "empty.txt"
            empty.write_text("  \n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "没有内容|Không trích xuất"):
                CONVERTER.convert_document_to_text(empty)

            unsupported = Path(folder) / "image.bin"
            unsupported.write_bytes(b"\x00\x01")
            with self.assertRaisesRegex(ValueError, "Chưa hỗ trợ định dạng"):
                CONVERTER.convert_document_to_text(unsupported)

    def test_original_file_is_not_modified(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "book.html"
            original = "<html><body><p>Không sửa file gốc</p></body></html>"
            source.write_text(original, encoding="utf-8")
            CONVERTER.convert_document_to_text(source)
            self.assertEqual(source.read_text(encoding="utf-8"), original)


if __name__ == "__main__":
    unittest.main()
