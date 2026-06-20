"""
test_pdf_handler.py — اختبارات وحدوية لـ pdf_handler.py
========================================================
تختبر دوال الاستخراج بدون اتصال شبكي (mock).
"""
import pytest
from pdf_handler import extract_file_id


class TestExtractFileId:
    """اختبارات extract_file_id()."""

    def test_standard_view_url(self):
        """رابط view عادي."""
        url = "https://drive.google.com/file/d/1aBcDeFgHiJkLmNoPqRsTuVwXyZ012345/view"
        assert extract_file_id(url) == "1aBcDeFgHiJkLmNoPqRsTuVwXyZ012345"

    def test_open_url(self):
        """رابط open?id=."""
        url = "https://drive.google.com/open?id=1aBcDeFgHiJkLmNoPqRsTuVwXyZ012345"
        assert extract_file_id(url) == "1aBcDeFgHiJkLmNoPqRsTuVwXyZ012345"

    def test_docs_url(self):
        """رابط Google Docs."""
        url = "https://docs.google.com/document/d/1aBcDeFgHiJkLmNoPqRsTuVwXyZ012345/edit"
        assert extract_file_id(url) == "1aBcDeFgHiJkLmNoPqRsTuVwXyZ012345"

    def test_empty_url(self):
        """رابط فارغ."""
        assert extract_file_id("") is None
        assert extract_file_id(None) is None

    def test_invalid_url(self):
        """رابط غير Google Drive."""
        assert extract_file_id("https://example.com/file.pdf") is None

    def test_short_id_rejected(self):
        """ID أقل من 25 حرف يُرفض."""
        url = "https://drive.google.com/file/d/shortID123/view"
        assert extract_file_id(url) is None

    def test_url_with_query_params(self):
        """رابط مع معاملات إضافية."""
        url = "https://drive.google.com/file/d/1aBcDeFgHiJkLmNoPqRsTuVwXyZ012345/view?usp=sharing"
        assert extract_file_id(url) == "1aBcDeFgHiJkLmNoPqRsTuVwXyZ012345"
