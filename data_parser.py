"""
data_parser.py
==============
يحوّل صفًّا من 117 عمودًا (قادمًا من Google Sheets) إلى كائن JSON منظّم.

البنية المتوقّعة للصف:
    [0]  Timestamp
    [1]  Office Name       اسم المكتب
    [2]  Submitter         اسم المُقدِّم
    [3]  Submitter Phone   رقم هاتف المُقدِّم
    [4]  Monthly Plan Link رابط PDF الخطة الشهرية

    [5 .. 114] Task Chunks (11 مهمة × 10 أعمدة)
        offset 0: مسؤول المهمة
        offset 1: هاتف المسؤول
        offset 2: اسم المهمة       ← يُستخدم للتحقق من وجود مهمة
        offset 3: الوصف
        offset 4: النوع
        offset 5: الآلية
        offset 6: الحالة
        offset 7: الإشكاليات
        offset 8: رابط الملف
        offset 9: "هل تريد إضافة مهمة أخرى؟" ← يُتجاهَل

    [115] General Challenges  التحديات العامة
    [116] Additional Notes    ملاحظات إضافية
"""

from __future__ import annotations
from typing import Any

import config as cfg


# ─── Types ──────────────────────────────────────────────────────────────────
TaskDict   = dict[str, str]
OfficeData = dict[str, Any]


# ─── Helpers ────────────────────────────────────────────────────────────────
def _safe_get(row: list[str], index: int, default: str = "") -> str:
    """إرجاع قيمة العمود بأمان مع التعامل مع الفهارس خارج النطاق."""
    try:
        return str(row[index]).strip()
    except (IndexError, TypeError):
        return default


def _is_empty(value: str) -> bool:
    """True إذا كانت القيمة فارغة أو تحتوي فراغات فقط."""
    return not value or not value.strip()


# ─── Task Parser ────────────────────────────────────────────────────────────
def _parse_task_chunk(row: list[str], chunk_start: int) -> TaskDict | None:
    """
    يُعالج chunk من 10 أعمدة ويُرجع قاموس المهمة.
    يُرجع None إذا كان اسم المهمة فارغًا.

    Args:
        row:         الصف الكامل من 117 عمودًا.
        chunk_start: فهرس بداية الـ chunk في الصف.

    Returns:
        قاموس المهمة أو None.
    """
    task_name = _safe_get(row, chunk_start + cfg.TASK_COL_TASK_NAME)
    if _is_empty(task_name):
        return None  # تجاهل الـ chunk الفارغة

    return {
        "manager":       _safe_get(row, chunk_start + cfg.TASK_COL_MANAGER),
        "manager_phone": _safe_get(row, chunk_start + cfg.TASK_COL_MANAGER_PHONE),
        "name":          task_name,
        "description":   _safe_get(row, chunk_start + cfg.TASK_COL_DESCRIPTION),
        "type":          _safe_get(row, chunk_start + cfg.TASK_COL_TYPE),
        "mechanism":     _safe_get(row, chunk_start + cfg.TASK_COL_MECHANISM),
        "status":        _safe_get(row, chunk_start + cfg.TASK_COL_STATUS),
        "issues":        _safe_get(row, chunk_start + cfg.TASK_COL_ISSUES),
        "file_link":     _safe_get(row, chunk_start + cfg.TASK_COL_FILE_LINK),
    }


# ─── Main Parser ────────────────────────────────────────────────────────────
def parse_row(row: list[str]) -> OfficeData:
    """
    يُحوّل صفًّا من 117 عمودًا إلى كائن JSON منظّم.

    Args:
        row: قائمة من السلاسل النصية (row من gspread).

    Returns:
        قاموس بالبيانات المهيكلة للمكتب.
    """
    # ── البيانات العامة ──────────────────────────────────────────────────────
    timestamp_str = _safe_get(row, getattr(cfg, 'COL_TIMESTAMP', 0))
    
    target_month_num = None

    MONTH_MAP = {
        1: 'كانون الثاني', 2: 'شباط', 3: 'آذار', 4: 'نيسان',
        5: 'أيار', 6: 'حزيران', 7: 'تموز', 8: 'آب',
        9: 'أيلول', 10: 'تشرين الأول', 11: 'تشرين الثاني', 12: 'كانون الأول'
    }

    target_month_name = ""
    if timestamp_str:
        try:
            month_part = ""
            if "-" in timestamp_str:
                month_part = timestamp_str.split("-")[1]
            elif "/" in timestamp_str:
                month_part = timestamp_str.split("/")[1]
            
            if month_part.isdigit():
                fallback_num = int(month_part)
                target_month_name = MONTH_MAP.get(fallback_num, "")
                target_month_num = fallback_num
        except Exception:
            pass

    office_data: OfficeData = {
        "timestamp":         timestamp_str,
        "target_month_num":  target_month_num,
        "target_month_name": target_month_name,
        "office_name":       _safe_get(row, getattr(cfg, 'COL_OFFICE_NAME', 1)),
        "submitter":         _safe_get(row, getattr(cfg, 'COL_SUBMITTER', 2)),
        "submitter_phone":   _safe_get(row, getattr(cfg, 'COL_SUBMITTER_PHONE', 3)),
        "monthly_plan_link": _safe_get(row, getattr(cfg, 'COL_MONTHLY_PLAN_LINK', 4)),
        "tasks":             [],
        "general_challenges":_safe_get(row, getattr(cfg, 'COL_GENERAL_CHALLENGES', 115)),
        "additional_notes":  _safe_get(row, getattr(cfg, 'COL_ADDITIONAL_NOTES', 116)),
    }

    # ── استخراج المهام ───────────────────────────────────────────────────────
    for task_number in range(cfg.MAX_TASKS):
        chunk_start = cfg.TASK_START_INDEX + (task_number * cfg.TASK_CHUNK_SIZE)
        task = _parse_task_chunk(row, chunk_start)
        if task:
            office_data["tasks"].append(task)

    return office_data


# ─── Statistics Helper ──────────────────────────────────────────────────────
def get_task_statistics(office_data: OfficeData) -> dict[str, Any]:
    """
    يُنشئ إحصائيات سريعة عن مهام المكتب (مفيدة لـ AI prompt).

    Args:
        office_data: المخرجات المباشرة من parse_row().

    Returns:
        قاموس بالإحصائيات.
    """
    tasks = office_data.get("tasks", [])
    if not tasks:
        return {"total": 0, "completed": 0, "in_progress": 0, "pending": 0,
                "has_issues": 0, "completion_rate": 0.0}

    completed  = sum(1 for t in tasks if "مكتمل" in t["status"] or "منجز" in t["status"])
    in_progress= sum(1 for t in tasks if "جارٍ" in t["status"] or "قيد" in t["status"])
    has_issues = sum(1 for t in tasks if not _is_empty(t["issues"]))

    return {
        "total":           len(tasks),
        "completed":       completed,
        "in_progress":     in_progress,
        "pending":         len(tasks) - completed - in_progress,
        "has_issues":      has_issues,
        "completion_rate": round(completed / len(tasks) * 100, 1),
    }


# ─── Quick Test ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import json

    # صف تجريبي فارغ (117 خانة)
    dummy_row = ["2025-01-01", "مكتب دمشق", "أحمد علي", "0900000001",
                 "http://plan-link.pdf"] + [""] * 112

    # إضافة مهمة تجريبية في الـ chunk الأولى (index 5)
    dummy_row[5]  = "محمد سالم"       # manager
    dummy_row[6]  = "0911111111"      # manager_phone
    dummy_row[7]  = "تنظيم محاضرة"   # task_name  ← الأساسي
    dummy_row[8]  = "محاضرة توعوية"  # description
    dummy_row[9]  = "ثقافي"          # type
    dummy_row[10] = "حضوري"          # mechanism
    dummy_row[11] = "مكتمل"          # status
    dummy_row[12] = ""               # issues
    dummy_row[13] = ""               # file_link

    result = parse_row(dummy_row)
    stats  = get_task_statistics(result)

    print("✅ Analysis Result:")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print("\n📊 Statistics:")
    print(json.dumps(stats, ensure_ascii=False, indent=2))
