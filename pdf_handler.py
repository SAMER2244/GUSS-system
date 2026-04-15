"""
pdf_handler.py
==============
وحدة استخراج نص خطة المكتب الشهرية من ملف PDF مُرفوع على Google Drive.

المسار الكامل:
    رابط Drive (col 4) → File ID → تحميل إلى الذاكرة (BytesIO)
    → استخراج النص بـ pdfplumber → إعادة سلسلة نصية نظيفة

المتطلبات:
    google-api-python-client, pdfplumber, google-auth
"""

from __future__ import annotations

import io
import re

import pdfplumber
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

import config as cfg


# ─── Drive Scopes ────────────────────────────────────────────────────────────
_DRIVE_SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
]


# ─── Drive Service ───────────────────────────────────────────────────────────
def _get_drive_service():
    """
    ينشئ ويُعيد خدمة Google Drive API مُصادَق عليها.

    Returns:
        googleapiclient Resource جاهز للاستخدام.

    Raises:
        FileNotFoundError: إذا لم يُعثر على credentials.json.
    """
    try:
        creds = Credentials.from_service_account_file(
            cfg.SERVICE_ACCOUNT_FILE,
            scopes=_DRIVE_SCOPES,
        )
    except FileNotFoundError:
        raise FileNotFoundError(
            f"❌ ملف الصلاحيات غير موجود: '{cfg.SERVICE_ACCOUNT_FILE}'"
        )
    return build("drive", "v3", credentials=creds, cache_discovery=False)


# ─── File ID Extractor ───────────────────────────────────────────────────────
def extract_file_id(drive_url: str) -> str | None:
    """
    يستخرج File ID من رابط Google Drive أو Google Docs/Forms.

    الأنماط المدعومة:
        - https://drive.google.com/file/d/FILE_ID/view
        - https://drive.google.com/open?id=FILE_ID
        - https://docs.google.com/...d/FILE_ID/...

    Args:
        drive_url: الرابط الكامل كما ورد في العمود الرابع.

    Returns:
        File ID كسلسلة نصية، أو None إذا فشل الاستخراج.
    """
    if not drive_url or not isinstance(drive_url, str):
        return None

    # النمط 1: /file/d/ID/ أو /d/ID/
    match = re.search(r"/d/([a-zA-Z0-9_-]{25,})", drive_url)
    if match:
        return match.group(1)

    # النمط 2: ?id=ID أو &id=ID
    match = re.search(r"[?&]id=([a-zA-Z0-9_-]{25,})", drive_url)
    if match:
        return match.group(1)

    return None


# ─── PDF Downloader ──────────────────────────────────────────────────────────
def _download_pdf_to_memory(service, file_id: str) -> bytes:
    """
    يُنزَّل PDF من Drive إلى الذاكرة مباشرةً (بدون حفظ على القرص).

    Args:
        service: خدمة Drive API.
        file_id: معرّف الملف.

    Returns:
        محتوى الملف كـ bytes.

    Raises:
        RuntimeError: عند فشل التنزيل.
    """
    request = service.files().get_media(fileId=file_id)
    buffer = io.BytesIO()
    downloader = MediaIoBaseDownload(buffer, request)

    done = False
    while not done:
        _, done = downloader.next_chunk()

    buffer.seek(0)
    return buffer.read()


# ─── Text Extractor ──────────────────────────────────────────────────────────
def _extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """
    يستخرج النص من ملف PDF ممثَّل كـ bytes.

    Args:
        pdf_bytes: محتوى الـ PDF كـ bytes.

    Returns:
        النص المستخرج كسلسلة نظيفة.
    """
    text_parts: list[str] = []

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text.strip())

    full_text = "\n\n".join(text_parts)

    # تنظيف: إزالة الأسطر الفارغة المتكررة
    full_text = re.sub(r"\n{3,}", "\n\n", full_text)
    return full_text.strip()


# ─── Public Interface ─────────────────────────────────────────────────────────
def get_plan_text(drive_url: str) -> tuple[str, str]:
    """
    الواجهة الرئيسية: يأخذ رابط Drive ويُعيد النص المستخرج من PDF.

    Args:
        drive_url: رابط Google Drive كما ورد في col 4 (index 4).

    Returns:
        Tuple[plan_text, status_message]:
            plan_text: النص المستخرج (فارغ عند الفشل).
            status_message: رسالة تصف نتيجة العملية (للتسجيل).

    لا يُطلق استثناءً أبدًا — يُعيد نصًا فارغًا ورسالة خطأ واضحة عند أي مشكلة.
    """
    # ── فحص الرابط ──────────────────────────────────────────────────────────
    if not drive_url or not drive_url.strip().startswith("http"):
        return "", "⚠️  لا يوجد رابط خطة شهرية في هذا الصف."

    file_id = extract_file_id(drive_url)
    if not file_id:
        return "", f"⚠️  تعذّر استخراج File ID من الرابط: {drive_url}"

    # ── تنزيل الـ PDF ────────────────────────────────────────────────────────
    try:
        service = _get_drive_service()
        pdf_bytes = _download_pdf_to_memory(service, file_id)
    except FileNotFoundError as e:
        return "", str(e)
    except Exception as e:
        return "", f"❌ فشل تنزيل PDF (ID: {file_id}): {e}"

    # ── استخراج النص ─────────────────────────────────────────────────────────
    try:
        text = _extract_text_from_pdf(pdf_bytes)
    except Exception as e:
        return "", f"❌ فشل قراءة نص PDF (ID: {file_id}): {e}"

    if not text:
        return "", f"⚠️  الـ PDF فارغ أو نصه غير قابل للاستخراج (ID: {file_id})."

    char_count = len(text)
    return text, f"✅ تم استخراج {char_count:,} حرف من PDF (ID: {file_id})"


# ─── Quick Test ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    test_urls = [
        "https://drive.google.com/file/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms/view",
        "https://drive.google.com/open?id=1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms",
        "",
        "invalid-url",
    ]
    for url in test_urls:
        fid = extract_file_id(url)
        print(f"URL: {url[:60]}...\n  → File ID: {fid}\n")
