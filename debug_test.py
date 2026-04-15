"""
debug_test.py — Dry-Run Sandbox
================================
اختبار شامل بدون اتصال بـ Google Sheets أو Drive.
يكشف بالضبط:
  1. ماذا يُمرَّر إلى الـ LLM (الـ prompt الكامل)
  2. ماذا يُعيد الـ LLM (الاستجابة الخام)
  3. هل يُستخرج الـ JSON بنجاح؟
  4. هل تطابق المهام يعمل؟
  5. هل التحديات والملاحظات تصل فعلًا؟
"""

import sys
import json
import re
from pathlib import Path

# ── تحميل الوحدات من مجلد المشروع ──────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))

from data_parser import parse_row, get_task_statistics
from ai_engine import _build_audit_prompt, _SYSTEM_INSTRUCTION, get_analyzer
from report_generator import _extract_task_insights

SEPARATOR = "=" * 70


# ─── 1. بناء صف تجريبي واقعي ────────────────────────────────────────────────
print(f"\n{SEPARATOR}")
print("  STEP 1 — Building dummy_row (117 columns)")
print(SEPARATOR)

dummy_row = [
    "2026/04/01",          # [0]  Timestamp
    "مكتب الاختبار",       # [1]  Office Name
    "سامر صالح",           # [2]  Submitter
    "0991234567",          # [3]  Phone
    "",                    # [4]  Monthly Plan Link (no PDF — tests fallback path)
] + [""] * 112             # [5-116] empty placeholders

# ── المهمة 1 ─────────────────────────────────────────────────────────────────
dummy_row[5]  = "ليلى حسن"          # manager
dummy_row[6]  = "0991111111"        # manager_phone
dummy_row[7]  = "تنظيم ورشة عمل قانونية"   # task_name
dummy_row[8]  = "ورشة تدريبية حول حقوق الطالب الجامعي استمرت ثلاث ساعات"
dummy_row[9]  = "تدريبي"            # type
dummy_row[10] = "حضوري في قاعة المؤتمرات"   # mechanism  ← الحقل المُسبِّب للنسخ
dummy_row[11] = "مكتمل"             # status
dummy_row[12] = "تأخر في توفير المعدات التقنية أثّر على الجداول الزمنية"  # issues

# ── المهمة 2 ─────────────────────────────────────────────────────────────────
dummy_row[15] = "أحمد كريم"
dummy_row[16] = "0992222222"
dummy_row[17] = "اجتماع تنسيق مع الجامعات"
dummy_row[18] = "اجتماع تنسيقي مع ممثلي خمس جامعات لمتابعة ملف القبول"
dummy_row[19] = "إداري"
dummy_row[20] = "إلكتروني عبر Zoom"   # mechanism  ← كلمة قصيرة قد تُنسخ حرفيًا
dummy_row[21] = "مكتمل"
dummy_row[22] = ""                   # no issues

# ── الحقول الختامية (الأكثر أهمية في الاختبار) ───────────────────────────────
dummy_row[115] = "شُحّ الموارد المالية يُعيق تنفيذ الأنشطة الميدانية، وغياب المقرّ الثابت يُضعف التنسيق الداخلي"
dummy_row[116] = "نأمل من القيادة مراجعة آلية تخصيص الميزانيات ودراسة إمكانية تأمين مقرّ دائم للمكتب"

print("✅ dummy_row built (117 columns)")
print(f"   Challenges : {dummy_row[115]}")
print(f"   Notes      : {dummy_row[116]}")


# ─── 2. تحليل الصف ──────────────────────────────────────────────────────────
print(f"\n{SEPARATOR}")
print("  STEP 2 — parse_row(dummy_row)")
print(SEPARATOR)

office_data = parse_row(dummy_row)

print(f"✅ office_name        : {office_data['office_name']}")
print(f"✅ target_month_name  : {office_data['target_month_name']}")
print(f"✅ tasks count        : {len(office_data['tasks'])}")
print(f"✅ general_challenges : {office_data.get('general_challenges', '[MISSING]')}")
print(f"✅ additional_notes   : {office_data.get('additional_notes',   '[MISSING]')}")


# ─── 3. بناء الـ prompt الكامل ──────────────────────────────────────────────
print(f"\n{SEPARATOR}")
print("  STEP 3 — _build_audit_prompt() → FULL PROMPT SENT TO LLM")
print(SEPARATOR)

plan_text = ""   # بدون PDF — يختبر المسار الأصعب
prompt = _build_audit_prompt(office_data, plan_text)

print(prompt)

# التحقق من وجود الحقلين في الـ prompt
challenges_in_prompt = office_data["general_challenges"] in prompt
notes_in_prompt      = office_data["additional_notes"]   in prompt
print(f"\n{'─'*50}")
print(f"🔍 Challenges IN Prompt? : {'✅ YES' if challenges_in_prompt else '❌ NO — BUG!'}")
print(f"🔍 Notes IN Prompt?      : {'✅ YES' if notes_in_prompt      else '❌ NO — BUG!'}")

# التحقق من أن الحقلين يأتيان بعد tasks_payload
json_pos       = prompt.rfind('"tasks"')
challenges_pos = prompt.find(office_data["general_challenges"])
notes_pos      = prompt.find(office_data["additional_notes"])
print(f"🔍 Challenges AFTER task JSON? : {'✅ YES' if challenges_pos > json_pos else '❌ NO — order bug!'}")
print(f"🔍 Notes AFTER task JSON?      : {'✅ YES' if notes_pos      > json_pos else '❌ NO — order bug!'}")


# ─── 4. اتصال حقيقي بالـ LLM ────────────────────────────────────────────────
print(f"\n{SEPARATOR}")
print("  STEP 4 — Live LLM call via get_analyzer().analyze()")
print(SEPARATOR)

analyzer = get_analyzer()
raw_response = analyzer.analyze(office_data, plan_text)

print(f"\n{'─'*50}")
print("  RAW LLM RESPONSE:")
print('─'*50)
print(raw_response)


# ─── 5. استخراج الـ JSON من الاستجابة ──────────────────────────────────────
print(f"\n{SEPARATOR}")
print("  STEP 5 — JSON Extraction & Task Matching")
print(SEPARATOR)

insight_index = _extract_task_insights(raw_response)
id_map   = insight_index["by_id"]
name_map = insight_index["by_name"]

print(f"✅ by_id   keys  : {list(id_map.keys())}")
print(f"✅ by_name keys  : {list(name_map.keys())}")

# اختبار مطابقة كل مهمة
for idx, task in enumerate(office_data["tasks"], start=1):
    t_name       = task.get("name", "").strip()
    t_name_lower = t_name.lower()

    ai_data = (
        id_map.get(str(idx))
        or name_map.get(t_name_lower)
        or next(
            (v for k, v in name_map.items()
             if t_name_lower in k or k in t_name_lower),
            {}
        )
    )
    insight = ai_data.get("ai_insight", "")
    match_method = (
        "task_id"  if id_map.get(str(idx)) else
        "exact"    if name_map.get(t_name_lower) else
        "contains" if ai_data else
        "MISS"
    )
    status = "✅" if insight else "❌ NO INSIGHT"
    print(f"  Task {idx} [{match_method:8s}] {status} | '{t_name[:35]}'")
    if insight:
        print(f"             → {insight[:80]}")


# ─── 6. فحص الحقلين في الاستجابة ───────────────────────────────────────────
print(f"\n{SEPARATOR}")
print("  STEP 6 — Did the LLM actually USE Challenges & Notes?")
print(SEPARATOR)

import unicodedata

def strip_tashkeel(text: str) -> str:
    """يُزيل علامات التشكيل (diacritics) للمقارنة المرنة."""
    return "".join(c for c in text if unicodedata.category(c) != "Mn")

response_normalized = strip_tashkeel(raw_response).lower()

# كلمات مفتاحية جوهرية (بدون تشكيل)
challenges_kw = strip_tashkeel("شح الموارد")       # جوهر التحدي
notes_kw      = strip_tashkeel("مقر دائم")          # جوهر الطلب

ch_found = challenges_kw.lower() in response_normalized
no_found = notes_kw.lower()      in response_normalized

print(f"🔍 Challenges keyword in response? : {'✅ YES — LLM read & used it!' if ch_found else '❌ NO — LLM ignored it!'}")
print(f"🔍 Notes keyword in response?      : {'✅ YES — LLM read & used it!' if no_found else '❌ NO — LLM ignored it!'}")

# إظهار السطور ذات الصلة من الاستجابة للتحقق اليدوي
print("\n📌 Relevant lines from LLM response (Challenges/Notes context):")
for line in raw_response.splitlines():
    normalized_line = strip_tashkeel(line).lower()
    if challenges_kw.lower() in normalized_line or notes_kw.lower() in normalized_line:
        print(f"   → {line.strip()}")

print(f"\n{SEPARATOR}")
print("  DIAGNOSTIC SUMMARY")
print(SEPARATOR)
print(f"  Prompt built correctly  : {'✅' if challenges_in_prompt and notes_in_prompt else '❌'}")
print(f"  Field order correct     : {'✅' if challenges_pos > json_pos else '❌'}")
print(f"  LLM received challenges : {'✅' if challenges_in_prompt else '❌'}")
print(f"  LLM used challenges     : {'✅' if ch_found else '❌ Ignored'}")
print(f"  LLM used notes          : {'✅' if no_found else '❌ Ignored'}")
print(f"  JSON extracted          : {'✅' if id_map or name_map else '❌ Parse failed'}")
print(f"  Task matching worked    : {'✅' if any(id_map.get(str(i+1)) or name_map.get(t.get('name','').lower()) for i,t in enumerate(office_data['tasks'])) else '⚠️ All misses'}")
print(SEPARATOR)
