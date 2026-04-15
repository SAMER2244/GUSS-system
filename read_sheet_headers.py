import gspread
from google.oauth2.service_account import Credentials

# =============================================
# الإعدادات - عدّل هذه القيم حسب مشروعك
# =============================================
SERVICE_ACCOUNT_FILE = "credentials.json"   # مسار ملف صلاحيات الـ Service Account
SPREADSHEET_NAME     = "نظام المتابعة الدوري - الاتحاد العام لطلبة سوريا"  # أو استخدم SPREADSHEET_URL أدناه
# SPREADSHEET_URL    = "https://docs.google.com/spreadsheets/d/..."

# الصلاحيات المطلوبة
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]


def get_sheet_headers():
    """الاتصال بـ Google Sheets وإرجاع أول سطر (العناوين)."""

    # 1. إنشاء الـ credentials من ملف الـ Service Account
    try:
        creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    except FileNotFoundError:
        raise FileNotFoundError(
            f"❌ ملف الصلاحيات غير موجود: '{SERVICE_ACCOUNT_FILE}'\n"
            "تأكد من تحميل ملف service_account.json ووضعه في نفس المجلد."
        )

    # 2. الاتصال بـ Google Sheets
    client = gspread.authorize(creds)

    # 3. فتح ملف الـ Spreadsheet
    try:
        # فتح بالاسم
        spreadsheet = client.open(SPREADSHEET_NAME)
        # أو فتح بالرابط (علّق السطر أعلاه وأفتِح التعليق أدناه)
        # spreadsheet = client.open_by_url(SPREADSHEET_URL)
    except gspread.SpreadsheetNotFound:
        raise PermissionError(
            f"❌ الملف '{SPREADSHEET_NAME}' غير موجود أو لا توجد صلاحية للوصول إليه.\n"
            "تأكد من:\n"
            "  1. صحة اسم الملف.\n"
            "  2. مشاركة الملف مع البريد الإلكتروني الموجود في service_account.json."
        )

    # 4. اختيار أول شيت
    sheet = spreadsheet.sheet1

    # 5. قراءة أول سطر (العناوين)
    headers = sheet.row_values(1)

    if not headers:
        print("⚠️  Sheet is empty or first row has no data.")
        return []

    return headers


def main():
    print("🔗 Connecting to Google Sheets...\n")
    try:
        headers = get_sheet_headers()
        print("✅ Connected successfully!\n")
        print(f"📋 Column count: {len(headers)}")
        print("📌 Column headers:")
        for i, header in enumerate(headers, start=1):
            print(f"   {i}. {header}")

    except FileNotFoundError as e:
        print(e)
    except PermissionError as e:
        print(e)
    except gspread.exceptions.APIError as e:
        print(f"❌ Google Sheets API error: {e}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")


if __name__ == "__main__":
    main()
