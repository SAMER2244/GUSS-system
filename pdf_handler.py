"""
pdf_handler.py  —  V2.2 (Supabase + Drive dual-source)
=======================================================
يُحمّل ملفات PDF ويستخرج النص منها من مصدرين:

  1. رابط Google Drive (/d/{ID}/ أو ?id={ID}):
     يستخدم Drive API v3 عبر Service Account للتنزيل.

  2. رابط HTTP مباشر (Supabase Signed URL أو أي URL آخر):
     يُنزَّل الملف مباشرة عبر httpx بدون أي تدخل Drive API.

مصمم ليكون «لا يفشل أبداً» — يُرجع دائماً (text, status).
"""

from __future__ import annotations

import io
import re

import httpx
import pdfplumber
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

import config as cfg
from logger import get_logger

_log = get_logger("pdf")

_DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]


# ─── Drive helpers ────────────────────────────────────────────────────────────

def _get_drive_service():
    """يُنشئ خدمة Drive API v3 مُصادَق عليها."""
    creds = Credentials.from_service_account_file(
        cfg.SERVICE_ACCOUNT_FILE, scopes=_DRIVE_SCOPES
    )
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def extract_file_id(drive_url: str) -> str | None:
    """
    يستخرج file_id من رابط Google Drive.

    يدعم:
      - /d/{ID}/
      - ?id={ID}

    يتطلب طول ID ≥ 25 حرف.
    """
    if not drive_url:
        return None
    patterns = [
        r"/d/([a-zA-Z0-9_-]{25,})",
        r"[?&]id=([a-zA-Z0-9_-]{25,})",
    ]
    for pat in patterns:
        m = re.search(pat, drive_url)
        if m:
            return m.group(1)
    return None


def _is_drive_url(url: str) -> bool:
    """يُحدِّد إذا كان الرابط رابط Google Drive يحتوي على file_id صالح."""
    return extract_file_id(url) is not None


def _download_from_drive(file_id: str) -> bytes:
    """يُحمّل PDF من Google Drive إلى الذاكرة عبر Drive API."""
    service = _get_drive_service()
    request = service.files().get_media(fileId=file_id)
    buffer = io.BytesIO()
    downloader = MediaIoBaseDownload(buffer, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    return buffer.getvalue()


def _download_from_http(url: str) -> bytes:
    """يُحمّل PDF من رابط HTTP مباشر (مثل Supabase Signed URL) إلى الذاكرة."""
    with httpx.Client(follow_redirects=True, timeout=60.0) as client:
        response = client.get(url)
        response.raise_for_status()
        return response.content


# ─── PDF text extraction ──────────────────────────────────────────────────────

def _extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """يستخرج النص من جميع صفحات PDF عبر pdfplumber."""
    text_parts: list[str] = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
    raw = "\n".join(text_parts)
    # تنظيف الأسطر الفارغة الزائدة
    return re.sub(r"\n{3,}", "\n\n", raw).strip()


# ─── Public API ───────────────────────────────────────────────────────────────

def get_plan_text(url: str) -> tuple[str, str]:
    """
    الواجهة العامة: URL → (نص_مُستخرج, رسالة_حالة).

    يدعم نوعين من الروابط:
      - رابط Google Drive: يستخدم Drive API عبر Service Account.
      - رابط HTTP مباشر (مثل Supabase Signed URL): تحميل مباشر عبر httpx.

    لا يرفع استثناءات أبداً — خط الأنابيب يستمر بدون مقارنة الخطة عند أي فشل.

    Args:
        url: رابط ملف PDF (Google Drive أو Supabase Signed URL أو أي HTTP URL).

    Returns:
        (extracted_text, status_message) — النص فارغ عند أي فشل.
    """
    if not url or not url.strip():
        _log.debug("لا يوجد رابط خطة شهرية")
        return "", "⚠️  لا يوجد رابط خطة شهرية."

    try:
        # ── تحديد مصدر التحميل ──────────────────────────────────────────────
        file_id = extract_file_id(url)

        if file_id:
            # مسار (a): رابط Google Drive
            _log.debug("تحميل PDF من Google Drive: file_id=%s", file_id)
            pdf_bytes = _download_from_drive(file_id)
            source_label = "Drive"
        else:
            # مسار (b): رابط HTTP مباشر (Supabase Signed URL وما شابهه)
            _log.debug("تحميل PDF عبر HTTP مباشر: %s", url[:80])
            pdf_bytes = _download_from_http(url)
            source_label = "HTTP"

        if not pdf_bytes:
            _log.warning("ملف PDF فارغ: %s", url[:60])
            return "", "⚠️  ملف PDF فارغ."

        text = _extract_text_from_pdf(pdf_bytes)

        if not text.strip():
            _log.warning("لم يُستخرج نص من PDF (%s): %s", source_label, url[:60])
            return "", "⚠️  PDF لا يحتوي على نص قابل للاستخراج."

        _log.info("✅ تم استخراج %d حرف من PDF [%s]", len(text), source_label)
        return text, ""

    except Exception as exc:
        _log.error("فشل معالجة PDF (%s): %s", url[:60], exc)
        return "", f"⚠️  فشل تحميل/قراءة PDF: {exc}"
