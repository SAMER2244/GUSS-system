"""
main.py  —  V2.0 Smart Auditing Pipeline
=========================================
نقطة الدخول الرئيسية لنظام توليد التقارير الآلي — V2.0.

خط الأنابيب المُحدَّث:
    Google Sheets → تحميل PDF من Drive → تحليل Gemini (مقارن) → تقرير Word
"""

from __future__ import annotations

import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

import config as cfg
from sheet_reader import get_all_data_rows
from data_parser import parse_row
from pdf_handler import get_plan_text
from ai_engine import get_orchestrator
from report_generator import build_report
from drive_uploader import upload_report



def _safe_filename(name: str) -> str:
    """
    يُحوّل اسم المكتب إلى اسم ملف آمن.

    Args:
        name: اسم المكتب الأصلي.

    Returns:
        سلسلة مناسبة لأسماء الملفات (Windows-safe).
    """
    safe = "".join(c if c.isalnum() or c in " _-" else "_" for c in name)
    return safe.strip().replace(" ", "_")


def _get_report_filename(office_data: dict, target_month_num: int = None) -> str:
    """
    يُنشئ اسم ملف التقرير: YYYY-MM_OfficeName.docx

    Args:
        office_data: البيانات المُهيكَلة من parse_row().
        target_month_num: رقم الشهر المحدد من المستخدم.

    Returns:
        اسم الملف مع امتداد .docx
    """
    if target_month_num:
        month_str = f"{datetime.now().year}-{target_month_num:02d}"
    else:
        month_str = datetime.now().strftime("%Y-%m")
        
    office_name = _safe_filename(office_data.get("office_name", "مكتب_غير_محدد"))
    return f"{month_str}_{office_name}.docx"


def _print_banner() -> None:
    """يُطبع رسالة الترحيب عند بدء التشغيل."""
    print("=" * 68)
    print("  Automated Report Generation System V2.0 — GUSS")
    print("  Smart Auditing: Monthly Plan PDF vs. Actual Performance")
    print("=" * 68)
    print(f"  📅 Date:            {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  📂 Reports Folder:  {cfg.REPORTS_DIR}")
    _model_line = (
        f"4-Thread Orchestrator | "
        f"Summary:{cfg.GROQ_MODEL_SUMMARY.split('-')[0]+'...'} | "
        f"Tasks:{cfg.GROQ_MODEL_TASKS.split('-')[0]+'...'} | "
        f"Audit:Gemini | Challenges:Gemma"
    )
    print(f"  🤖 AI Engine:       {_model_line}")
    print("=" * 68 + "\n")


# ─── Interactive Office Selector ──────────────────────────────────────────────
def display_office_menu(rows: list[list]) -> list[list]:
    """
    يعرض قائمة تفاعلية بأسماء المكاتب ويطلب من المستخدم تحديد ما يريد معالجته.

    Args:
        rows: صفوف البيانات الخام من Google Sheets.

    Returns:
        قائمة الصفوف المختارة فقط (مرتّبة حسب الاختيار).
    """
    def _office_name(row: list) -> str:
        return row[1].strip() if len(row) > 1 and row[1].strip() else "غير محدد"

    def _timestamp(row: list) -> str:
        return row[0].strip()[:16] if len(row) > 0 and row[0].strip() else "—"

    total = len(rows)

    print()
    print("╔" + "═" * 62 + "╗")
    print("║  🏛️  Select Offices to Process" + " " * 29 + "║")
    print("╚" + "═" * 62 + "╝")
    print(f"  {'ID':<4} | {'Office':<32} | Timestamp")
    print(f"  {'-'*4}-+-{'-'*32}-+-{'-'*16}")

    for i, row in enumerate(rows, start=1):
        name = _office_name(row)
        ts   = _timestamp(row)
        print(f"  {i:<4} | {name:<32} | {ts}")

    print()
    print(f"  Total offices: {total}")
    print("  IDs separated by commas or spaces  [ex: 1, 3]  or  'all'  for all")
    print()

    valid_ids = set(range(1, total + 1))

    while True:
        raw = input("  ➤ Selection: ").strip()

        if not raw:
            print("  ⚠️  No input. Please try again.")
            continue

        if raw.lower() == "all":
            print(f"  ✅ All {total} offices selected.")
            print()
            return rows

        parts = raw.replace(",", " ").split()
        parsed: list[int] = []
        invalid: list[str] = []

        for p in parts:
            if p.isdigit():
                n = int(p)
                if n in valid_ids:
                    if n not in parsed:
                        parsed.append(n)
                else:
                    invalid.append(p)
            else:
                invalid.append(p)

        if invalid:
            print(f"  ❌ Invalid IDs: {', '.join(invalid)}")
            print(f"  IDs must be between 1 and {total}. Please try again.")
            continue

        if not parsed:
            print("  ⚠️  No valid ID entered. Please try again.")
            continue

        selected = [rows[i - 1] for i in sorted(parsed)]
        names    = [_office_name(r) for r in selected]
        print(f"  ✅ Selected: {', '.join(names)}")
        print()
        return selected

def get_target_month() -> tuple[int, str]:
    """
    يسأل المستخدم لإدخال رقم الشهر (1-12) ويُرجِع الرقم واسم الشهر بالعربية.
    """
    months_ar = {
        1: "كانون الثاني", 2: "شباط", 3: "آذار", 4: "نيسان",
        5: "أيار", 6: "حزيران", 7: "تموز", 8: "آب",
        9: "أيلول", 10: "تشرين الأول", 11: "تشرين الثاني", 12: "كانون الأول"
    }
    while True:
        raw = input("  ➤ Which month is this report for? (Enter number 1-12): ").strip()
        if raw.isdigit():
            m = int(raw)
            if 1 <= m <= 12:
                name = months_ar[m]
                print(f"  ✅ Month selected: {name}")
                print()
                return m, name
        print("  ⚠️  Invalid input. Enter a number between 1 and 12.")



# ─── Validation ──────────────────────────────────────────────────────────────
def _validate_environment() -> None:
    """
    يتحقق من المتطلبات الأساسية قبل بدء المعالجة.

    Raises:
        SystemExit: إذا كانت بيانات الاعتماد أو مفتاح API مفقودًا.
    """
    errors: list[str] = []

    if not Path(cfg.SERVICE_ACCOUNT_FILE).exists():
        errors.append(
            f"❌ credentials.json not found at: {cfg.SERVICE_ACCOUNT_FILE}"
        )

    if cfg.LLM_PROVIDER == "GROQ":
        if not cfg.GROQ_API_KEYS:
            errors.append(
                "❌ لا يوجد أي مفتاح Groq API.\n"
                "   أضف GROQ_API_KEYS=key1,key2 إلى ملف .env\n"
                "   https://console.groq.com/keys"
            )
    else:
        if not cfg.GEMINI_API_KEY or cfg.GEMINI_API_KEY == "YOUR_GEMINI_API_KEY_HERE":
            errors.append(
                "❌ GEMINI_API_KEY is not set. Add it to your .env file."
            )

    if errors:
        print("\n".join(errors))
        sys.exit(1)


# ─── Pipeline ────────────────────────────────────────────────────────────────
def run_pipeline() -> None:
    """
    يُشغّل خط الأنابيب الكامل لمعالجة جميع صفوف الـ Spreadsheet.

    خطوات V2.0 لكل صف:
        1. تحليل بيانات الصف (parse_row).
        2. تحميل وتحليل PDF الخطة الشهرية (get_plan_text) — مع Fallback.
        3. إرسال البيانات + نص الخطة إلى Gemini (analyze).
        4. إنشاء تقرير Word احترافي (build_report).
    """
    _print_banner()
    _validate_environment()

    # ── 1. جلب البيانات من Sheets ─────────────────────────────────────────
    print("📡 Connecting to Google Sheets...\n")
    try:
        rows = get_all_data_rows()
    except (FileNotFoundError, PermissionError, ValueError) as e:
        print(e)
        sys.exit(1)

    print(f"✅ Fetched {len(rows)} rows\n")

    # ── اختيار المكاتب التفاعلي ───────────────────────────────────────────────
    selected_rows = display_office_menu(rows)

    # ── اختيار الشهر التفاعلي ─────────────────────────────────────────────────
    target_month_num, target_month_name = get_target_month()

    # ── 2. تهيئة المنظّم التوازي ───────────────────────────────────
    print("🤖 Initializing 4-Thread Orchestrator...\n")
    try:
        orchestrator = get_orchestrator()
    except (ValueError, ImportError) as e:
        print(e)
        sys.exit(1)

    # ── 3. معالجة كل صف ──────────────────────────────────────────────────
    success_count    = 0
    error_count      = 0
    skipped_count    = 0
    pdf_missing_count = 0

    for row_index, raw_row in enumerate(selected_rows, start=1):
        print(f"\n{'─' * 55}")
        print(f"🔄 Processing {row_index}/{len(selected_rows)}...")

        try:
            # أ) تحليل بيانات الصف
            office_data  = parse_row(raw_row)
            office_name  = office_data.get("office_name", "")
            
            # حُقن الشهر المختار ليتم استخدامه في بناء التقرير ورفع الملفات
            office_data["target_month_name"] = target_month_name

            if not office_name:
                print(f"   ⚠️  Row {row_index}: Office name empty — skipping.")
                skipped_count += 1
                continue

            if not office_data.get("tasks"):
                print(f"   ⚠️  Row {row_index} ({office_name}): No tasks found — skipping.")
                skipped_count += 1
                continue

            print(f"   📋 Office: {office_name} | Tasks: {len(office_data['tasks'])}")

            # ب) تحميل PDF الخطة الشهرية (مع Fallback)
            drive_url = office_data.get("monthly_plan_link", "")
            print(f"   📄 Loading plan PDF ({drive_url[:55] or 'no link'})...")
            plan_text, pdf_status = get_plan_text(drive_url)

            if plan_text:
                print(f"   {pdf_status}")
            else:
                print(f"   {pdf_status}  ← Pipeline continues without plan comparison.")
                pdf_missing_count += 1

            # ج) التحليل المتوازي — 4 خيوط مع Live Progress Tracker
            _status: dict[str, str] = {
                "summary":    "⏳",
                "tasks":      "⏳",
                "audit":      "⏳",
                "challenges": "⏳",
            }
            _labels = {
                "summary":    "Summary",
                "tasks":      "Tasks",
                "audit":      "Audit",
                "challenges": "Challenges",
            }

            def _print_progress() -> None:
                parts = " | ".join(
                    f"{_labels[s]}: {_status[s]}"
                    for s in ["summary", "tasks", "audit", "challenges"]
                )
                print(f"\r   [{office_name}] {parts}   ", end="", flush=True)

            def _on_progress(section: str, ok: bool) -> None:
                _status[section] = "✅" if ok else "❌"
                _print_progress()

            _print_progress()   # عرض السطر الأول
            office_results = orchestrator.analyze(
                office_data, plan_text, on_progress=_on_progress
            )
            print()   # Newline after tracker

            # د) إنشاء التقرير
            filename    = _get_report_filename(office_data, target_month_num)
            output_path = cfg.REPORTS_DIR / filename
            build_report(
                office_data,
                office_results,
                output_path,
                plan_text=plan_text,
                pdf_status=pdf_status,
            )

            success_count += 1

            # هـ) رفع التقرير والمرفقات إلى Google Drive
            try:
                upload_report(output_path, office_name, office_data=office_data)
            except Exception as upload_err:
                print(f"   ⚠️  Drive upload failed: {upload_err}")
                print("   💡 Report saved locally in reports/")
        except Exception:
            error_count += 1
            print(f"   ❌ Unexpected error in row {row_index}:")
            traceback.print_exc()

        # ── Cooldown: فترة انتظار إلزامية بين الصفوف لتفادي 429 ──────────────
        if row_index < len(selected_rows):
            cooldown = 10   # ثانية
            print(f"\n   ⏳ Cooldown: {cooldown}s", end="", flush=True)
            for _ in range(cooldown):
                time.sleep(1)
                print(".", end="", flush=True)
            print(" ✓")

    # ── 4. ملخص النتائج ───────────────────────────────────────────────────
    print(f"\n{'=' * 68}")
    print("  📊 Pipeline Summary V2.0")
    print(f"{'=' * 68}")
    print(f"  ✅ Reports generated:         {success_count}")
    print(f"  📄 With plan PDF:             {success_count - pdf_missing_count}")
    print(f"  ⚠️  Without plan PDF:          {pdf_missing_count}")
    print(f"  ⏭️  Rows skipped:              {skipped_count}")
    print(f"  ❌ Errors:                     {error_count}")
    print(f"  📂 Reports Folder:               {cfg.REPORTS_DIR}")
    print(f"{'=' * 68}\n")

    if success_count == 0:
        print("⚠️  No reports generated. Check messages above.")
    else:
        print(f"🎉 Done! {success_count} audit report(s) saved to 'reports/'")
        if pdf_missing_count > 0:
            print(
                f"💡 تنبيه: {pdf_missing_count} مكتب لم يرفع خطة PDF."
                " تحقق من صلاحيات Drive وصحة الروابط في العمود الخامس."
            )


# ─── Entry Point ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    run_pipeline()
