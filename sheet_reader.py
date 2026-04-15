"""
sheet_reader.py
===============
وحدة الاتصال بـ Google Sheets وجلب البيانات.
تُوفّر client مُعاد الاستخدام وقراءة الصفوف بأكملها.
"""

from __future__ import annotations

import time

import gspread
from google.oauth2.service_account import Credentials

import config as cfg

# تكوين المحاولات والأخطاء العابرة للإعادة
_RETRY_MAX:   int   = 3
_RETRY_BASE:  float = 5.0    # 5s → 10s → 20s


# ─── Client ─────────────────────────────────────────────────────────────────
def get_gspread_client() -> gspread.Client:
    """
    ينشئ ويُرجع gspread Client مُصادَق عليه.

    Returns:
        gspread.Client جاهز للاستخدام.

    Raises:
        FileNotFoundError: إذا لم يُعثر على ملف credentials.json.
    """
    try:
        creds = Credentials.from_service_account_file(
            cfg.SERVICE_ACCOUNT_FILE, scopes=cfg.SCOPES
        )
    except FileNotFoundError:
        raise FileNotFoundError(
            f"❌ ملف الصلاحيات غير موجود: '{cfg.SERVICE_ACCOUNT_FILE}'\n"
            "تأكد من وضع credentials.json في نفس مجلد المشروع."
        )
    return gspread.authorize(creds)


def _open_spreadsheet(client: gspread.Client) -> gspread.Spreadsheet:
    """
    يفتح ملف الـ Spreadsheet بالاسم أو بالرابط.
    يُعيد المحاولة تلقائيًا عند 503/500 حتى _RETRY_MAX مرات.

    Raises:
        PermissionError: إذا لم يُعثر على الملف أو لا توجد صلاحية.
    """
    for attempt in range(1, _RETRY_MAX + 1):
        try:
            return client.open(cfg.SPREADSHEET_NAME)
            # أو بالرابط: return client.open_by_url(cfg.SPREADSHEET_URL)
        except gspread.SpreadsheetNotFound:
            raise PermissionError(
                f"❌ الملف '{cfg.SPREADSHEET_NAME}' غير موجود أو لا توجد صلاحية للوصول.\u202f\n"
                "تأكد من:\n"
                "  1. صحة اسم الملف في config.py\n"
                "  2. مشاركة الشيت مع البريد الموجود في credentials.json"
            )
        except gspread.exceptions.APIError as exc:
            status = getattr(exc.response, "status_code", 0)
            if status in (500, 503) and attempt < _RETRY_MAX:
                wait = int(_RETRY_BASE * (2 ** (attempt - 1)))   # 5s, 10s, 20s
                print(f"   ⏳ [Google Sheets {status}] Temp service error — retrying {attempt}/{_RETRY_MAX}",
                      end="", flush=True)
                for _ in range(wait):
                    time.sleep(1)
                    print(".", end="", flush=True)
                print(" ✓")
                client = get_gspread_client()   # أعد بناء العميل لتجنب جلسة منتهية الصلاحية
            else:
                raise   # خطأ غير 503 أو استُنفدت المحاولات
    raise RuntimeError("❌ فشل الاتصال بـ Google Sheets بعد جميع المحاولات.")


# ─── Header reader ──────────────────────────────────────────────────────────
def get_sheet_headers() -> list[str]:
    """
    يقرأ السطر الأول (العناوين) من أول شيت.

    Returns:
        قائمة بأسماء الأعمدة.
    """
    client = get_gspread_client()
    sheet  = _open_spreadsheet(client).sheet1
    headers = sheet.row_values(1)
    if not headers:
        print("⚠️  Sheet is empty or first row has no data.")
    return headers


# ─── Data reader ────────────────────────────────────────────────────────────
def get_all_data_rows() -> list[list[str]]:
    """
    يجلب كل صفوف البيانات (السطر الثاني فصاعدًا) من أول شيت.
    يُعيد المحاولة تلقائيًا عند 503/500 حتى _RETRY_MAX مرات.

    Returns:
        قائمة من الصفوف، كل صف قائمة من السلاسل النصية.

    Raises:
        ValueError: إذا لم تكن هناك بيانات في الشيت.
    """
    for attempt in range(1, _RETRY_MAX + 1):
        try:
            client = get_gspread_client()
            sheet  = _open_spreadsheet(client).sheet1
            all_values: list[list[str]] = sheet.get_all_values()

            if len(all_values) <= 1:
                raise ValueError(
                    "⚠️  لا توجد بيانات في الشيت (فارغ أو يحتوي على عناوين فحسب)."
                )

            data_rows = all_values[1:]
            print(f"✅ Fetched {len(data_rows)} data rows.")
            return data_rows

        except ValueError:
            raise   # لا تُعاد المحاولة على بيانات فارغة — هذا خطأ منطقي
        except gspread.exceptions.APIError as exc:
            status = getattr(exc.response, "status_code", 0)
            if status in (500, 503) and attempt < _RETRY_MAX:
                wait = int(_RETRY_BASE * (2 ** (attempt - 1)))   # 5s, 10s, 20s
                print(f"   ⏳ [Google Sheets {status}] Temp service error — retrying {attempt}/{_RETRY_MAX}",
                      end="", flush=True)
                for _ in range(wait):
                    time.sleep(1)
                    print(".", end="", flush=True)
                print(" ✓")
            else:
                raise   # خطأ غير 503 أو استُنفدت المحاولات
        except (PermissionError, RuntimeError):
            raise   # لا تُعاد المحاولة على أخطاء الصلاحية

    raise RuntimeError("❌ فشل جلب بيانات Google Sheets بعد جميع المحاولات.")


# ─── Quick test ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("🔗 Connecting to Google Sheets...\n")
    try:
        headers = get_sheet_headers()
        print(f"✅ Connected successfully!\n📋 Column count: {len(headers)}")
        for i, h in enumerate(headers, 1):
            print(f"   {i:>3}. {h}")
    except (FileNotFoundError, PermissionError) as e:
        print(e)
    except gspread.exceptions.APIError as e:
        print(f"❌ Google Sheets API error: {e}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
