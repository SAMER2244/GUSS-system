"""
check_migration_progress.py — متابعة تقدم معالجة الـ AI بعد الترحيل
======================================================================

الاستخدام:
    # أحدث batch تلقائياً:
    python check_migration_progress.py

    # batch محدد:
    python check_migration_progress.py data/migration/batch_20260711_190000.json

    # مراقبة مستمرة كل 30 ثانية:
    python check_migration_progress.py --watch
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import config as cfg
from database import get_supabase_client

BASE_DIR = Path(__file__).parent
MIGRATION_DIR = BASE_DIR / "data" / "migration"
WATCH_INTERVAL = 30   # ثانية


# ─── جلب أحدث ملف batch ──────────────────────────────────────────────────────

def find_latest_batch(migration_dir: Path) -> Path | None:
    """يجد أحدث ملف batch في مجلد الترحيل."""
    files = sorted(migration_dir.glob("batch_*.json"), reverse=True)
    return files[0] if files else None


def load_batch(batch_path: Path) -> dict:
    """يُحمّل ملف batch."""
    import json
    with open(batch_path, "r", encoding="utf-8") as f:
        return json.load(f)


# ─── استعلام الحالة من Supabase ─────────────────────────────────────────────

def query_queue_status(db, submission_ids: list[int]) -> list[dict]:
    """يستعلم ai_processing_queue عن حالة قائمة submission_ids."""
    if not submission_ids:
        return []
    result = (
        db.table("ai_processing_queue")
        .select("submission_id, status, error_message, processed_at")
        .in_("submission_id", submission_ids)
        .execute()
    )
    return result.data or []


# ─── تقرير التقدم ─────────────────────────────────────────────────────────────

def print_progress_report(
    batch_data: dict,
    queue_rows: list[dict],
    batch_path: Path,
) -> bool:
    """
    يطبع تقرير التقدم.
    يُعيد True إذا اكتمل الكل (done أو failed) — لإيقاف --watch.
    """
    all_ids: list[int] = batch_data.get("submission_ids", [])
    total = len(all_ids)
    if total == 0:
        print("⚠️  ملف batch فارغ — لا توجد submissions للمتابعة.")
        return True

    # بناء قاموس: submission_id → row
    status_map = {r["submission_id"]: r for r in queue_rows}

    # إحصاء الحالات
    counts = {"pending": 0, "processing": 0, "done": 0, "failed": 0, "not_found": 0}
    failed_items: list[dict] = []

    for sid in all_ids:
        row = status_map.get(sid)
        if row is None:
            counts["not_found"] += 1
        else:
            status = row.get("status", "not_found")
            counts[status] = counts.get(status, 0) + 1
            if status == "failed":
                failed_items.append(row)

    done_count = counts["done"]
    failed_count = counts["failed"]
    remaining = total - done_count - failed_count

    # ─── شريط التقدم النصي ───────────────────────────────────────────────────
    bar_width = 40
    filled = int(bar_width * done_count / total) if total > 0 else 0
    bar = "█" * filled + "░" * (bar_width - filled)

    now_str = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")

    print(f"\n{'═'*70}")
    print(f"  📊 تقدم معالجة الـ AI — {now_str}")
    print(f"  ملف: {batch_path.name}")
    print(f"{'─'*70}")
    print(f"  [{bar}] {done_count}/{total}")
    print(f"{'─'*70}")
    print(f"  ✅ مكتملة  (done)       : {counts['done']:4d}")
    print(f"  🔄 قيد المعالجة (processing): {counts['processing']:4d}")
    print(f"  ⏳ بانتظار  (pending)    : {counts['pending']:4d}")
    print(f"  ❌ فشل      (failed)     : {counts['failed']:4d}")
    if counts["not_found"]:
        print(f"  ❓ غير موجود (not found): {counts['not_found']:4d}")

    # ─── تقدير الوقت المتبقي ──────────────────────────────────────────────────
    pending_count = counts["pending"]
    if pending_count > 0:
        est_seconds = pending_count * cfg.QUEUE_MIN_DELAY_SECONDS
        est_minutes = est_seconds / 60
        print(f"\n  ⏱️  تقدير الوقت المتبقي (تقريبي جداً):")
        print(f"     {pending_count} صف × {cfg.QUEUE_MIN_DELAY_SECONDS}s = ~{est_seconds}s (~{est_minutes:.1f} دقيقة)")
        print(f"     ⚠️  هذا تقدير لا يحسب أوقات معالجة الـ AI الفعلية أو حالات إعادة المحاولة.")

    # ─── قائمة الفاشلة ───────────────────────────────────────────────────────
    if failed_items:
        print(f"\n  {'─'*68}")
        print(f"  ❌ submissions بحالة FAILED ({len(failed_items)}):\n")
        for item in failed_items:
            sid = item["submission_id"]
            err = item.get("error_message") or "(لا رسالة خطأ)"
            proc_at = item.get("processed_at") or "—"
            print(f"     submission_id={sid}")
            print(f"     آخر خطأ: {err[:120]}")
            print(f"     processed_at: {proc_at}\n")

    print(f"{'═'*70}\n")

    # اكتمل الكل إذا لم يبقَ pending أو processing
    return (counts["pending"] + counts["processing"]) == 0


# ─── النقطة الرئيسية ──────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="متابعة تقدم معالجة الـ AI بعد الترحيل."
    )
    parser.add_argument(
        "batch_file",
        nargs="?",
        help="مسار ملف batch (اختياري — يختار أحدث ملف تلقائياً)",
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help=f"إعادة الاستعلام كل {WATCH_INTERVAL}s حتى الاكتمال",
    )
    args = parser.parse_args()

    # ─── تحديد ملف batch ─────────────────────────────────────────────────────
    if args.batch_file:
        batch_path = Path(args.batch_file)
    else:
        batch_path = find_latest_batch(MIGRATION_DIR)
        if batch_path is None:
            print(f"❌ لا توجد ملفات batch في: {MIGRATION_DIR}")
            print("   شغّل migrate_legacy_data.py --commit أولاً.")
            sys.exit(1)
        print(f"📂 أحدث ملف batch: {batch_path}")

    if not batch_path.exists():
        print(f"❌ الملف غير موجود: {batch_path}")
        sys.exit(1)

    batch_data = load_batch(batch_path)

    try:
        db = get_supabase_client()
    except RuntimeError as e:
        print(f"❌ تعذّر الاتصال بـ Supabase: {e}")
        sys.exit(1)

    all_ids: list[int] = batch_data.get("submission_ids", [])

    if not args.watch:
        # ─── تشغيل واحد فقط ──────────────────────────────────────────────────
        queue_rows = query_queue_status(db, all_ids)
        print_progress_report(batch_data, queue_rows, batch_path)
    else:
        # ─── مراقبة مستمرة ───────────────────────────────────────────────────
        print(f"👀 وضع --watch: استعلام كل {WATCH_INTERVAL}s — اضغط Ctrl+C للإيقاف\n")
        try:
            while True:
                queue_rows = query_queue_status(db, all_ids)
                completed = print_progress_report(batch_data, queue_rows, batch_path)
                if completed:
                    print("🎉 اكتملت جميع المهام!")
                    break
                print(f"⏰ الاستعلام التالي خلال {WATCH_INTERVAL}s...\n")
                time.sleep(WATCH_INTERVAL)
        except KeyboardInterrupt:
            print("\n⛔ تم إيقاف المراقبة.")


if __name__ == "__main__":
    main()
