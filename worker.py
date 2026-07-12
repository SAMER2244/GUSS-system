"""
worker.py — AI Processing Queue Worker
=======================================
يعالج صفوف ai_processing_queue بشكل غير متزامن عن خادم الويب.

الاستخدام:
    python worker.py

يُشغَّل بشكل مستقل عن web_server.py ويمكن تشغيله يدوياً أو عبر خدمة نظام.
يقرأ جميع إعدادات التأخير والمحاولات من config.py (مصدرها settings.yaml).
"""

from __future__ import annotations

import signal
import sys
import time
import traceback
from datetime import datetime, timezone, timedelta

import config as cfg
from database import get_supabase_client
from logger import get_logger
from web_server import _background_pipeline_runner

_log = get_logger("worker")

# ─── إشارة الإيقاف النظيف ───────────────────────────────────────────────────
# يُضبط على True عند استلام SIGTERM/SIGINT — يمنع التقاط صف جديد
_shutdown_requested: bool = False


def _handle_signal(signum, frame) -> None:
    """معالج SIGTERM/SIGINT: يطلب الإيقاف بعد انتهاء المعالجة الجارية."""
    global _shutdown_requested
    sig_name = signal.Signals(signum).name
    _log.info(f"📴 Signal {sig_name} received — finishing current job then exiting.")
    _shutdown_requested = True


signal.signal(signal.SIGTERM, _handle_signal)
signal.signal(signal.SIGINT, _handle_signal)


def recover_stuck_rows(db) -> None:
    """
    يُعيد الصفوف العالقة بحالة 'processing' إلى 'pending' عند بدء التشغيل.

    الصف العالق: status='processing' و created_at أقدم من
    cfg.QUEUE_STUCK_THRESHOLD_MINUTES وهذا يعني أن المعالجة السابقة
    تُوقّفت قسراً في منتصفها.
    """
    threshold_time = (
        datetime.now(timezone.utc)
        - timedelta(minutes=cfg.QUEUE_STUCK_THRESHOLD_MINUTES)
    ).isoformat()

    try:
        stuck = (
            db.table("ai_processing_queue")
            .select("id, submission_id, created_at")
            .eq("status", "processing")
            .lt("created_at", threshold_time)
            .execute()
        )

        if not stuck.data:
            _log.info("✅ No stuck 'processing' rows found on startup.")
            return

        for row in stuck.data:
            db.table("ai_processing_queue").update(
                {"status": "pending", "error_message": "Recovered from stuck 'processing' state on worker restart."}
            ).eq("id", row["id"]).execute()
            _log.warning(
                f"♻️  Recovered stuck row: queue_id={row['id']}, "
                f"submission_id={row['submission_id']}, "
                f"created_at={row['created_at']}"
            )

        _log.info(f"♻️  Recovered {len(stuck.data)} stuck row(s) to 'pending'.")

    except Exception as e:
        _log.error(f"❌ Error during stuck-row recovery: {e}\n{traceback.format_exc()}")


def fetch_next_pending(db):
    """
    يسحب أقدم صف 'pending' من الطابور.

    يستخدم SELECT مع ترتيب created_at تصاعدياً (FIFO).
    ملاحظة: Supabase Python client لا يدعم FOR UPDATE SKIP LOCKED مباشرةً؛
    الحماية من التعارض تتم عبر الانتقال الذري لـ status='processing' مباشرة
    بعد الجلب. لو شُغّل instance ثانٍ بالخطأ، أحدهما سيجد الصف محوّلاً
    بالفعل وسيتجاهله (فحص مزدوج بعد التحديث).
    """
    try:
        result = (
            db.table("ai_processing_queue")
            .select("id, submission_id, attempts")
            .eq("status", "pending")
            .order("created_at", desc=False)
            .limit(1)
            .execute()
        )
        return result.data[0] if result.data else None
    except Exception as e:
        _log.error(f"❌ Error fetching next pending row: {e}")
        return None


def claim_row(db, queue_id: int) -> bool:
    """
    يحوّل الصف إلى 'processing' بشكل ذري.
    يُعيد True عند النجاح، False إذا لم يجد الصف (تعارض محتمل مع instance آخر).
    """
    try:
        result = (
            db.table("ai_processing_queue")
            .update({"status": "processing"})
            .eq("id", queue_id)
            .eq("status", "pending")   # شرط ذري: لا ينجح إلا إذا كان لا يزال pending
            .execute()
        )
        return bool(result.data)
    except Exception as e:
        _log.error(f"❌ Error claiming queue row {queue_id}: {e}")
        return False


def mark_done(db, queue_id: int) -> None:
    """يُحدّث الصف إلى status='done' مع processed_at=NOW()."""
    try:
        db.table("ai_processing_queue").update({
            "status": "done",
            "processed_at": datetime.now(timezone.utc).isoformat(),
            "error_message": None,
        }).eq("id", queue_id).execute()
    except Exception as e:
        _log.error(f"❌ Failed to mark queue row {queue_id} as done: {e}")


def mark_failed_final(db, queue_id: int, error_msg: str, attempts: int) -> None:
    """يُحدّث الصف إلى status='failed' النهائي (تجاوز الحد الأقصى للمحاولات)."""
    try:
        db.table("ai_processing_queue").update({
            "status": "failed",
            "processed_at": datetime.now(timezone.utc).isoformat(),
            "error_message": error_msg[:2000],   # قيد طول رسالة الخطأ
            "attempts": attempts,
        }).eq("id", queue_id).execute()
    except Exception as e:
        _log.error(f"❌ Failed to mark queue row {queue_id} as failed: {e}")


def mark_retry(db, queue_id: int, error_msg: str, attempts: int) -> None:
    """يُعيد الصف إلى 'pending' مع تسجيل رسالة الخطأ وزيادة عداد المحاولات."""
    try:
        db.table("ai_processing_queue").update({
            "status": "pending",
            "error_message": error_msg[:2000],
            "attempts": attempts,
        }).eq("id", queue_id).execute()
    except Exception as e:
        _log.error(f"❌ Failed to reset queue row {queue_id} to pending: {e}")


def process_one(db, row: dict) -> int:
    """
    يعالج صفاً واحداً من الطابور.

    المنطق:
    1. يدّعي الصف (claim) ذرياً
    2. يستدعي _background_pipeline_runner (مسار المعالجة الكامل)
    3. عند النجاح → done
    4. عند الفشل → retry أو failed نهائي

    يُعيد مدة الانتظار المطلوبة (بالثواني) قبل التقاط الصف التالي:
      - نجاح        → QUEUE_MIN_DELAY_SECONDS
      - فشل نهائي  → QUEUE_MIN_DELAY_SECONDS
      - retry       → backoff_delay (أكبر من min_delay)
      - claim فاشل → 0 (تجاهل، لا انتظار إضافي)

    الانتظار الفعلي يتم دائماً في run_worker() لا هنا.
    """
    queue_id = row["id"]
    submission_id = row["submission_id"]
    attempts = row["attempts"]

    # ─── الادعاء الذري ──────────────────────────────────────────────────────
    if not claim_row(db, queue_id):
        _log.warning(
            f"⚠️  Row queue_id={queue_id} was already claimed by another process — skipping."
        )
        return 0   # لا انتظار — الصف لم يُعالج هنا

    _log.info(
        f"🔄 Processing: queue_id={queue_id}, submission_id={submission_id}, "
        f"attempt={attempts + 1}/{cfg.QUEUE_MAX_ATTEMPTS}"
    )
    start_time = time.monotonic()

    try:
        # ─── تشغيل مسار المعالجة الكامل ─────────────────────────────────────
        # _background_pipeline_runner يُنفَّذ هنا مباشرةً (ليس في خيط FastAPI)
        _background_pipeline_runner(submission_id=submission_id)

        elapsed = time.monotonic() - start_time
        _log.info(
            f"✅ Done: queue_id={queue_id}, submission_id={submission_id}, "
            f"elapsed={elapsed:.1f}s"
        )
        mark_done(db, queue_id)
        return cfg.QUEUE_MIN_DELAY_SECONDS

    except Exception as e:
        elapsed = time.monotonic() - start_time
        error_msg = f"{type(e).__name__}: {e}"
        new_attempts = attempts + 1

        _log.error(
            f"❌ Failed: queue_id={queue_id}, submission_id={submission_id}, "
            f"attempt={new_attempts}/{cfg.QUEUE_MAX_ATTEMPTS}, "
            f"elapsed={elapsed:.1f}s\n"
            f"   Error: {error_msg}\n"
            f"{traceback.format_exc()}"
        )

        if new_attempts >= cfg.QUEUE_MAX_ATTEMPTS:
            # فشل نهائي — تجاوز الحد الأقصى
            _log.error(
                f"🚫 Max attempts reached for queue_id={queue_id} — marking as FAILED."
            )
            mark_failed_final(db, queue_id, error_msg, new_attempts)
            return cfg.QUEUE_MIN_DELAY_SECONDS
        else:
            # إعادة للطابور — يُحسب الـ backoff ويُعاد للحلقة لتنتظره
            backoff_delay = (
                cfg.QUEUE_MIN_DELAY_SECONDS
                * (cfg.QUEUE_BACKOFF_MULTIPLIER ** new_attempts)
            )
            _log.info(
                f"⏳ Retry scheduled: queue_id={queue_id} will be retried "
                f"after ~{backoff_delay}s (backoff attempt {new_attempts})."
            )
            mark_retry(db, queue_id, error_msg, new_attempts)
            # الانتظار الفعلي سيتم في run_worker() عبر القيمة المُعادة
            return backoff_delay


def _interruptible_sleep(seconds: float) -> None:
    """
    ينتظر المدة المحددة مع فحص إشارة الإيقاف كل ثانية.
    يتوقف مبكراً إذا طُلب الإيقاف.
    """
    end_time = time.monotonic() + seconds
    while time.monotonic() < end_time and not _shutdown_requested:
        time.sleep(min(1.0, end_time - time.monotonic()))


# ─── الحلقة الرئيسية ────────────────────────────────────────────────────────
def run_worker() -> None:
    """حلقة العمل الرئيسية للـ worker."""
    _log.info("=" * 60)
    _log.info("🚀 GUSS AI Processing Worker starting...")
    _log.info(
        f"   Config: max_attempts={cfg.QUEUE_MAX_ATTEMPTS}, "
        f"min_delay={cfg.QUEUE_MIN_DELAY_SECONDS}s, "
        f"backoff_multiplier={cfg.QUEUE_BACKOFF_MULTIPLIER}x"
    )
    _log.info("=" * 60)

    # ─── الاتصال بقاعدة البيانات ─────────────────────────────────────────────
    try:
        db = get_supabase_client()
        _log.info("✅ Supabase client connected.")
    except RuntimeError as e:
        _log.critical(f"❌ Cannot connect to Supabase: {e}")
        sys.exit(1)

    # ─── استرجاع الصفوف العالقة من تشغيل سابق ───────────────────────────────
    recover_stuck_rows(db)

    # ─── الحلقة الرئيسية ─────────────────────────────────────────────────────
    _log.info("👀 Worker is now polling the queue...")
    idle_logged = False

    while not _shutdown_requested:
        row = fetch_next_pending(db)

        if row is None:
            if not idle_logged:
                _log.info("💤 Queue is empty — waiting for new submissions...")
                idle_logged = True
            # انتظار قصير قبل الفحص التالي (لا داعي للـ min_delay كاملاً عند الخمول)
            _interruptible_sleep(5)
            continue

        idle_logged = False   # إعادة الـ flag عند وجود عمل
        cooldown = process_one(db, row)

        # ─── صمام الأمان: انتظار مضمون بعد أي معالجة ────────────────────────
        # يُطبَّق على النجاح والفشل المؤقت والفشل النهائي على حدٍّ سواء.
        # cooldown=0 فقط عند فشل claim_row (لم تحدث معالجة فعلية).
        if cooldown > 0 and not _shutdown_requested:
            _log.info(
                f"⏸️  Cooldown: waiting {cooldown}s before next pick-up "
                f"(rate-limit guard)..."
            )
            _interruptible_sleep(cooldown)

    _log.info("🛑 Shutdown signal processed — worker exiting cleanly.")


if __name__ == "__main__":
    run_worker()
