"""
database.py — Supabase Connection Manager
==========================================
وحدة اتصال مستقلة بقاعدة بيانات Supabase.
تُنشئ عميل (client) واحد كـ singleton وتُعيد استخدامه.

الاستخدام:
    from database import get_supabase_client
    db = get_supabase_client()
    result = db.table("offices").select("*").execute()
"""

from __future__ import annotations

import os
from supabase import create_client, Client
from logger import get_logger

_log = get_logger("database")

# ─── Singleton Client ───────────────────────────────────────────────────────
_client: Client | None = None


def get_supabase_client() -> Client:
    """
    يُعيد عميل Supabase مُهيَّأ (singleton).
    يقرأ SUPABASE_URL و SUPABASE_ANON_KEY من متغيرات البيئة.

    Raises:
        RuntimeError: إذا لم يتم تعيين متغيرات البيئة المطلوبة.
    """
    global _client

    if _client is not None:
        return _client

    url = os.getenv("SUPABASE_URL", "").strip()
    key = os.getenv("SUPABASE_ANON_KEY", "").strip()

    if not url or not key:
        raise RuntimeError(
            "متغيرات البيئة SUPABASE_URL و SUPABASE_ANON_KEY مطلوبة "
            "للاتصال بقاعدة البيانات. يرجى تعيينها في ملف .env"
        )

    _client = create_client(url, key)
    _log.info("✅ Supabase client initialized successfully.")
    return _client


def create_signed_url(bucket: str, path: str, expires_in: int = 3600) -> str:
    """
    يُنشئ رابط موقَّع (signed URL) لملف في Supabase Storage.

    Args:
        bucket: اسم الـ bucket (مثل 'monthly-plans')
        path: مسار الملف داخل الـ bucket
        expires_in: مدة صلاحية الرابط بالثواني (افتراضي: ساعة واحدة)

    Returns:
        رابط موقَّع مؤقت للملف.

    Raises:
        RuntimeError: إذا فشل إنشاء الرابط.
    """
    client = get_supabase_client()
    result = client.storage.from_(bucket).create_signed_url(path, expires_in)

    if isinstance(result, dict) and "signedURL" in result:
        return result["signedURL"]
    elif isinstance(result, dict) and "error" in result:
        raise RuntimeError(f"فشل إنشاء رابط موقَّع: {result['error']}")

    # supabase-py v2+ returns an object with signedUrl
    if hasattr(result, "signed_url"):
        return result.signed_url

    return str(result)
