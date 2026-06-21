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

    def test_supabase_signed_url_returns_none(self):
        """رابط Supabase Signed URL لا يحتوي على file_id من Drive → يُرجع None."""
        url = (
            "https://xxxx.supabase.co/storage/v1/object/sign/monthly-plans/"
            "20260620_abc123.pdf?token=eyJhbGciOiJIUzI1NiJ9.fake"
        )
        assert extract_file_id(url) is None


class TestIsDriveUrl:
    """اختبارات _is_drive_url()."""

    def test_drive_url_detected(self):
        """رابط Drive صالح يُعرَّف كـ Drive URL."""
        from pdf_handler import _is_drive_url
        url = "https://drive.google.com/file/d/1aBcDeFgHiJkLmNoPqRsTuVwXyZ012345/view"
        assert _is_drive_url(url) is True

    def test_supabase_url_not_drive(self):
        """رابط Supabase Signed URL لا يُعرَّف كـ Drive URL."""
        from pdf_handler import _is_drive_url
        url = (
            "https://xxxx.supabase.co/storage/v1/object/sign/monthly-plans/"
            "20260620_abc123.pdf?token=eyJhbGciOiJIUzI1NiJ9.fake"
        )
        assert _is_drive_url(url) is False

    def test_plain_http_url_not_drive(self):
        """رابط HTTP عادي لا يُعرَّف كـ Drive URL."""
        from pdf_handler import _is_drive_url
        assert _is_drive_url("https://example.com/plan.pdf") is False


class TestGetPlanTextSupabase:
    """اختبار مسار Supabase/HTTP في get_plan_text مع محاكاة كاملة."""

    def test_supabase_url_downloads_via_http(self, mocker):
        """
        يتحقق من أن get_plan_text تستخدم _download_from_http (لا Drive API)
        عند استقبال رابط Supabase Signed URL، وتُرجع النص المستخرج بنجاح.
        """
        import io
        from unittest.mock import MagicMock
        from pdf_handler import get_plan_text

        # محاكاة _download_from_http لإرجاع bytes وهمية
        fake_pdf_bytes = b"%PDF-1.4 fake"
        mock_http_download = mocker.patch(
            "pdf_handler._download_from_http",
            return_value=fake_pdf_bytes,
        )

        # محاكاة _extract_text_from_pdf لإرجاع نص وهمي بدون فتح ملف PDF حقيقي
        fake_text = "نص الخطة الشهرية التجريبي للاختبار"
        mocker.patch(
            "pdf_handler._extract_text_from_pdf",
            return_value=fake_text,
        )

        # التأكد من عدم استدعاء Drive API أبداً
        mock_drive = mocker.patch("pdf_handler._download_from_drive")

        supabase_url = (
            "https://xxxx.supabase.co/storage/v1/object/sign/monthly-plans/"
            "20260620_abc123.pdf?token=eyJhbGciOiJIUzI1NiJ9.fake"
        )

        text, status = get_plan_text(supabase_url)

        # التحقق من النتائج
        assert text == fake_text
        assert "✅" in status
        assert str(len(fake_text)) in status

        # التحقق من أن المسار الصحيح استُخدم
        mock_http_download.assert_called_once_with(supabase_url)
        mock_drive.assert_not_called()

    def test_empty_url_returns_empty(self):
        """رابط فارغ → يُرجع نصاً فارغاً مع رسالة تحذير."""
        from pdf_handler import get_plan_text
        text, status = get_plan_text("")
        assert text == ""
        assert "⚠️" in status

    def test_supabase_url_http_failure_returns_empty(self, mocker):
        """فشل تحميل HTTP → يُرجع نصاً فارغاً بدون رفع استثناء."""
        from pdf_handler import get_plan_text
        mocker.patch(
            "pdf_handler._download_from_http",
            side_effect=Exception("Connection refused"),
        )
        url = "https://xxxx.supabase.co/storage/v1/object/sign/monthly-plans/plan.pdf?token=abc"
        text, status = get_plan_text(url)
        assert text == ""
        assert "⚠️" in status
