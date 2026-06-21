"""
pdf_handler.py  —  V2.1 (Logging + Exceptions)
================================================
يُحمّل ملفات PDF من Google Drive ويستخرج النص منها.
مصمم ليكون «لا يفشل أبداً» — يُرجع دائماً (text, status).
"""

from __future__ import annotations

import io
import re

import pdfplumber
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

import config as cfg
from logger import get_logger

_log = get_logger("pdf")

_DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]


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


def _download_pdf_to_memory(service, file_id: str) -> bytes:
    """يُحمّل PDF مباشرةً إلى الذاكرة (بدون حفظ محلي)."""
    request = service.files().get_media(fileId=file_id)
    buffer = io.BytesIO()
    downloader = MediaIoBaseDownload(buffer, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    return buffer.getvalue()


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


def get_plan_text(drive_url: str) -> tuple[str, str]:
    """
    الواجهة العامة: Drive URL → (نص_مُستخرج, رسالة_حالة).

    لا يرفع استثناءات أبداً — خط الأنابيب يستمر بدون مقارنة الخطة.

    Args:
        drive_url: رابط ملف PDF على Google Drive.

    Returns:
        (extracted_text, status_message) — النص فارغ عند أي فشل.
    """
    if not drive_url or not drive_url.strip():
        _log.debug("لا يوجد رابط خطة شهرية")
        return "", "⚠️  لا يوجد رابط خطة شهرية."

    # ── [DIAG] سطر تشخيصي مؤقت — يُحذف بعد التشخيص ──────────────────────
    _log.warning("[DIAG] get_plan_text called | url_prefix=%s", drive_url[:80])
    # ───────────────────────────────────────────────────────────────────────

    file_id = extract_file_id(drive_url)

    # ── [DIAG] سطر تشخيصي مؤقت — يُحذف بعد التشخيص ──────────────────────
    _log.warning("[DIAG] extract_file_id result: %s", file_id)
    # ───────────────────────────────────────────────────────────────────────

    if not file_id:
        _log.warning("رابط Drive غير صالح: %s", drive_url[:60])
        return "", f"⚠️  رابط Drive غير صالح: {drive_url[:60]}"

    try:
        _log.debug("تحميل PDF: file_id=%s", file_id)
        service = _get_drive_service()
        pdf_bytes = _download_pdf_to_memory(service, file_id)

        if not pdf_bytes:
            _log.warning("ملف PDF فارغ: %s", file_id)
            return "", "⚠️  ملف PDF فارغ."

        text = _extract_text_from_pdf(pdf_bytes)

        # ── [DIAG] سطر تشخيصي مؤقت — يُحذف بعد التشخيص ──────────────────────
        _log.warning(
            "[DIAG] PDF extraction | len=%d | first100=%r | status_will_be=%s",
            len(text),
            text[:100],
            "empty" if not text.strip() else "ok",
        )
        # ───────────────────────────────────────────────────────────────────────

        if not text.strip():
            _log.warning("لم يُستخرج نص من PDF: %s", file_id)
            return "", "⚠️  PDF لا يحتوي على نص قابل للاستخراج."

        _log.info("✅ تم استخراج %d حرف من PDF", len(text))
        status = f"✅ تم استخراج نص الخطة ({len(text)} حرف)"

        # ── [DIAG] سطر تشخيصي مؤقت — يُحذف بعد التشخيص ──────────────────────
        _log.warning("[DIAG] Returning pdf_status=%s", status)
        # ───────────────────────────────────────────────────────────────────────

        return text, status

    except Exception as exc:
        _log.error("فشل معالجة PDF (%s): %s", file_id, exc)
        return "", f"⚠️  فشل تحميل/قراءة PDF: {exc}"
