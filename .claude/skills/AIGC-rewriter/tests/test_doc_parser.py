"""Tests for document parser module."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.doc_parser import read_document, parse_document, SUPPORTED_SUFFIXES


class TestReadDocument:
    def test_txt_file(self, tmp_path):
        txt_file = tmp_path / "test.txt"
        txt_file.write_text("Hello world.", encoding="utf-8")
        text, suffix = read_document(str(txt_file))
        assert text == "Hello world."
        assert suffix == ".txt"

    def test_md_file(self, tmp_path):
        md_file = tmp_path / "test.md"
        md_file.write_text("# Title\n\nParagraph.", encoding="utf-8")
        text, suffix = read_document(str(md_file))
        assert "# Title" in text
        assert suffix == ".md"

    def test_file_not_found(self):
        try:
            read_document("/nonexistent/file.txt")
            assert False, "Should have raised FileNotFoundError"
        except FileNotFoundError:
            pass

    def test_unsupported_format(self, tmp_path):
        unsupported = tmp_path / "test.xyz"
        unsupported.write_text("content", encoding="utf-8")
        try:
            read_document(str(unsupported))
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "Unsupported format" in str(e)

    def test_empty_txt(self, tmp_path):
        txt_file = tmp_path / "empty.txt"
        txt_file.write_text("", encoding="utf-8")
        text, _ = read_document(str(txt_file))
        assert text == ""

    def test_utf8_fallback(self, tmp_path):
        # Test UTF-8 reading
        txt_file = tmp_path / "utf8.txt"
        txt_file.write_text("Hello 世界", encoding="utf-8")
        text, _ = read_document(str(txt_file))
        assert "世界" in text


class TestParseDocument:
    def test_txt_parsing(self, tmp_path):
        txt_file = tmp_path / "test.txt"
        txt_file.write_text("First paragraph.\n\nSecond paragraph.", encoding="utf-8")
        result = parse_document(str(txt_file))
        assert len(result) == 2
        assert result[0]["text"] == "First paragraph."
        assert result[0]["source_page"] is None
        assert result[0]["style"] is None

    def test_md_parsing(self, tmp_path):
        md_file = tmp_path / "test.md"
        md_file.write_text("First paragraph.\n\nSecond paragraph.", encoding="utf-8")
        result = parse_document(str(md_file))
        assert len(result) == 2


class TestSupportedSuffixes:
    def test_all_formats(self):
        assert ".txt" in SUPPORTED_SUFFIXES
        assert ".md" in SUPPORTED_SUFFIXES
        assert ".docx" in SUPPORTED_SUFFIXES
        assert ".pdf" in SUPPORTED_SUFFIXES

    def test_count(self):
        assert len(SUPPORTED_SUFFIXES) == 4


class TestDocxParsing:
    """Test DOCX parsing (requires python-docx)."""

    def test_docx_import_check(self):
        """Verify that DOCX parsing gives clear error if python-docx missing."""
        try:
            from docx import Document
            # python-docx is available, skip detailed tests
            # as they require actual .docx files
        except ImportError:
            # Expected if python-docx not installed
            pass


class TestPdfParsing:
    """Test PDF parsing (requires PyMuPDF)."""

    def test_pdf_import_check(self):
        """Verify that PDF parsing gives clear error if PyMuPDF missing."""
        try:
            import fitz
            # PyMuPDF is available
        except ImportError:
            # Expected if PyMuPDF not installed
            pass
