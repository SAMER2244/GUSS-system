"""
test_worker.py — اختبارات وحدوية للـ worker وسلوك الـ endpoint الجديد
======================================================================
تغطي:
  1. نجاح معالجة صف واحد (pending → processing → done)
  2. فشل مع إعادة المحاولة (attempts يزيد، يرجع pending)
  3. فشل نهائي بعد تجاوز الحد الأقصى (status → failed)
  4. استرجاع صفوف 'processing' العالقة عند بدء التشغيل
  5. الـ endpoint المعدّل يضيف صفاً بالطابور ولا يستدعي مسار المعالجة مباشرة

لا يوجد اتصال فعلي بقاعدة البيانات — كل الوصول للـ Supabase مُحاكى.
"""

from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock, call
from datetime import datetime, timezone, timedelta

import config as cfg


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _make_queue_row(
    queue_id: int = 1,
    submission_id: int = 42,
    attempts: int = 0,
    status: str = "pending",
) -> dict:
    """ينشئ صف طابور وهمي للاختبارات."""
    return {
        "id": queue_id,
        "submission_id": submission_id,
        "attempts": attempts,
        "status": status,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def _db_with_pending(row: dict):
    """
    ينشئ mock لعميل Supabase يُعيد صفاً واحداً من ai_processing_queue
    عند أول استدعاء لـ fetch_next_pending، ثم None بعدها.
    """
    db = MagicMock()

    # ─ fetch_next_pending: select().eq().order().limit().execute()
    pending_result = MagicMock()
    pending_result.data = [row]

    empty_result = MagicMock()
    empty_result.data = []

    # نبني كل مسار الـ chain
    def build_select_chain(data_result):
        chain = MagicMock()
        chain.eq.return_value = chain
        chain.order.return_value = chain
        chain.limit.return_value = chain
        chain.lt.return_value = chain
        chain.execute.return_value = data_result
        return chain

    pending_chain = build_select_chain(pending_result)
    empty_chain = build_select_chain(empty_result)

    # الاستدعاء الأول يُعيد الصف، والثاني يُعيد فارغاً
    select_mock = MagicMock()
    select_mock.side_effect = [pending_chain, empty_chain, empty_chain, empty_chain]

    table_mock = MagicMock()
    table_mock.select = select_mock
    table_mock.update.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(data=[row])
    table_mock.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[row])

    db.table.return_value = table_mock
    return db


# ─── 1. نجاح معالجة صف واحد (pending → done) ─────────────────────────────

class TestProcessOneSuccess:
    """pending → processing → done."""

    @patch("worker.get_supabase_client")
    @patch("worker._background_pipeline_runner")
    def test_process_one_success_calls_pipeline(self, mock_runner, mock_get_db):
        """يتحقق من استدعاء _background_pipeline_runner بـ submission_id الصحيح."""
        from worker import process_one

        db = MagicMock()
        # claim_row: update().eq().eq().execute() يُعيد الصف (نجاح)
        db.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(data=[{"id": 1}])
        # mark_done: update().eq().execute()
        db.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[{"id": 1}])

        row = _make_queue_row(queue_id=1, submission_id=42, attempts=0)
        mock_runner.return_value = None   # pipeline نجح بدون استثناء

        result = process_one(db, row)

        # process_one تُعيد مدة الانتظار (int) لا bool
        assert result == cfg.QUEUE_MIN_DELAY_SECONDS
        mock_runner.assert_called_once_with(submission_id=42)

    @patch("worker.get_supabase_client")
    @patch("worker._background_pipeline_runner")
    def test_process_one_success_marks_done(self, mock_runner, mock_get_db):
        """يتحقق من تغيير الحالة إلى done عند النجاح."""
        from worker import process_one, mark_done

        db = MagicMock()
        db.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(data=[{"id": 1}])
        db.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()

        row = _make_queue_row(queue_id=5, submission_id=99, attempts=0)
        mock_runner.return_value = None

        with patch("worker.mark_done") as mock_mark_done:
            process_one(db, row)
            mock_mark_done.assert_called_once_with(db, 5)


# ─── 2. فشل مع إعادة المحاولة ───────────────────────────────────────────────

class TestProcessOneRetry:
    """فشل دون تجاوز QUEUE_MAX_ATTEMPTS → pending مع backoff."""

    @patch("worker._interruptible_sleep")
    @patch("worker.get_supabase_client")
    @patch("worker._background_pipeline_runner")
    def test_retry_increments_attempts(self, mock_runner, mock_get_db, mock_sleep):
        """يتحقق من زيادة attempts عند الفشل."""
        from worker import process_one

        db = MagicMock()
        db.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(data=[{"id": 1}])
        db.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()

        mock_runner.side_effect = RuntimeError("Gemini API timeout")

        row = _make_queue_row(queue_id=2, submission_id=55, attempts=0)

        with patch("worker.mark_retry") as mock_retry, \
             patch("worker.mark_failed_final") as mock_final:
            process_one(db, row)
            # يجب استدعاء mark_retry (ليس mark_failed_final) عند الفشل الأول
            mock_retry.assert_called_once()
            mock_final.assert_not_called()

            # mark_retry signature: (db, queue_id, error_msg, attempts)
            # positional args: [0]=db, [1]=queue_id, [2]=error_msg, [3]=attempts
            call_args = mock_retry.call_args
            assert call_args[0][3] == 1   # new_attempts=1

    @patch("worker._interruptible_sleep")
    @patch("worker.get_supabase_client")
    @patch("worker._background_pipeline_runner")
    def test_retry_returns_false(self, mock_runner, mock_get_db, mock_sleep):
        """يتحقق من إعادة False (لم يكتمل) عند إعادة الجدولة."""
        from worker import process_one

        db = MagicMock()
        db.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(data=[{"id": 1}])
        db.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()

        mock_runner.side_effect = ValueError("Some transient error")
        row = _make_queue_row(queue_id=3, submission_id=77, attempts=0)

        with patch("worker.mark_retry"):
            result = process_one(db, row)
            # نتيجة retry: مدة الـ backoff (> 0, > QUEUE_MIN_DELAY_SECONDS)
            backoff = cfg.QUEUE_MIN_DELAY_SECONDS * (cfg.QUEUE_BACKOFF_MULTIPLIER ** 1)
            assert result == backoff

    @patch("worker.get_supabase_client")
    @patch("worker._background_pipeline_runner")
    def test_backoff_delay_uses_config(self, mock_runner, mock_get_db):
        """يتحقق من أن القيمة المُعادة من process_one هي backoff_delay المحسوبة من config.py."""
        from worker import process_one

        db = MagicMock()
        db.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(data=[{"id": 1}])
        db.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()

        mock_runner.side_effect = RuntimeError("error")
        row = _make_queue_row(queue_id=4, submission_id=88, attempts=0)

        with patch("worker.mark_retry"):
            result = process_one(db, row)

        # القيمة المُعادة يجب أن تساوي backoff_delay = min_delay * (multiplier ** new_attempts)
        expected_delay = cfg.QUEUE_MIN_DELAY_SECONDS * (cfg.QUEUE_BACKOFF_MULTIPLIER ** 1)
        assert result == expected_delay, (
            f"Expected return={expected_delay}, got={result}"
        )


# ─── 3. فشل نهائي بعد تجاوز الحد الأقصى ────────────────────────────────────

class TestProcessOneFinalFailure:
    """تجاوز QUEUE_MAX_ATTEMPTS → failed نهائي."""

    @patch("worker._interruptible_sleep")
    @patch("worker.get_supabase_client")
    @patch("worker._background_pipeline_runner")
    def test_final_failure_marks_failed(self, mock_runner, mock_get_db, mock_sleep):
        """يتحقق من انتقال الصف لـ failed عند تجاوز الحد الأقصى."""
        from worker import process_one

        db = MagicMock()
        db.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(data=[{"id": 1}])
        db.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()

        mock_runner.side_effect = Exception("Critical failure")

        # المحاولة تبدأ من attempts = max-1 (المحاولة الأخيرة)
        row = _make_queue_row(
            queue_id=6,
            submission_id=111,
            attempts=cfg.QUEUE_MAX_ATTEMPTS - 1
        )

        with patch("worker.mark_failed_final") as mock_final, \
             patch("worker.mark_retry") as mock_retry:
            result = process_one(db, row)
            mock_final.assert_called_once()
            mock_retry.assert_not_called()
            # فشل نهائي يُعيد QUEUE_MIN_DELAY_SECONDS (وليس True)
            assert result == cfg.QUEUE_MIN_DELAY_SECONDS

    @patch("worker._interruptible_sleep")
    @patch("worker.get_supabase_client")
    @patch("worker._background_pipeline_runner")
    def test_final_failure_no_backoff_sleep(self, mock_runner, mock_get_db, mock_sleep):
        """لا يجب أن يكون هناك backoff sleep عند الفشل النهائي."""
        from worker import process_one

        db = MagicMock()
        db.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(data=[{"id": 1}])
        db.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()

        mock_runner.side_effect = Exception("Final error")
        row = _make_queue_row(
            queue_id=7,
            submission_id=222,
            attempts=cfg.QUEUE_MAX_ATTEMPTS - 1
        )

        with patch("worker.mark_failed_final"), \
             patch("worker._interruptible_sleep") as mock_isleep:
            process_one(db, row)
            # لا يجب استدعاء _interruptible_sleep داخل process_one
            # (الانتظار يتم في run_worker() فقط)
            mock_isleep.assert_not_called()


# ─── 4. استرجاع الصفوف العالقة عند بدء التشغيل ─────────────────────────────

class TestRecoverStuckRows:
    """recover_stuck_rows: يُعيد الصفوف العالقة من processing إلى pending."""

    @patch("worker.get_supabase_client")
    def test_recover_stuck_rows_resets_to_pending(self, mock_get_db):
        """يتحقق من إعادة صفوف 'processing' العالقة إلى 'pending'."""
        from worker import recover_stuck_rows

        db = MagicMock()

        # الصفوف العالقة
        stuck_result = MagicMock()
        stuck_result.data = [
            {"id": 10, "submission_id": 101, "created_at": "2026-07-10T10:00:00+00:00"},
            {"id": 11, "submission_id": 102, "created_at": "2026-07-10T11:00:00+00:00"},
        ]

        # مسار: select().eq().lt().execute()
        db.table.return_value.select.return_value.eq.return_value.lt.return_value.execute.return_value = stuck_result
        db.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()

        recover_stuck_rows(db)

        # يجب استدعاء update مرتين (مرة لكل صف)
        assert db.table.return_value.update.call_count == 2

        # التحقق من أن الحالة أُعيدت إلى pending
        for update_call in db.table.return_value.update.call_args_list:
            assert update_call[0][0]["status"] == "pending"

    @patch("worker.get_supabase_client")
    def test_recover_stuck_rows_no_stuck(self, mock_get_db):
        """لا يوجد صفوف عالقة — لا يجب استدعاء update."""
        from worker import recover_stuck_rows

        db = MagicMock()

        empty_result = MagicMock()
        empty_result.data = []
        db.table.return_value.select.return_value.eq.return_value.lt.return_value.execute.return_value = empty_result

        recover_stuck_rows(db)

        db.table.return_value.update.assert_not_called()

    @patch("worker.get_supabase_client")
    def test_recover_stuck_rows_handles_db_error(self, mock_get_db):
        """خطأ في قاعدة البيانات لا يُوقف بدء التشغيل."""
        from worker import recover_stuck_rows

        db = MagicMock()
        db.table.return_value.select.return_value.eq.return_value.lt.return_value.execute.side_effect = Exception("DB error")

        # يجب ألا يرفع استثناء
        try:
            recover_stuck_rows(db)
        except Exception:
            pytest.fail("recover_stuck_rows raised an exception unexpectedly")


# ─── 5. الـ endpoint يُدرج في الطابور ولا يستدعي المعالجة مباشرة ─────────────

class TestEndpointQueuesInsteadOfDirect:
    """
    يتحقق من أن POST /api/submit-report لا يستدعي _background_pipeline_runner
    مباشرة بعد التعديل، بل يُدرج صفاً في ai_processing_queue.
    """

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from web_server import app
        return TestClient(app)

    def _make_db_mock(self):
        """ينشئ mock للـ Supabase يُحاكي جميع العمليات المطلوبة."""
        mock_db = MagicMock()

        mock_office_res = MagicMock()
        mock_office_res.data = [{"id": 3}]

        mock_sub_res = MagicMock()
        mock_sub_res.data = [{"id": 77}]

        mock_queue_res = MagicMock()
        mock_queue_res.data = [{"id": 99, "submission_id": 77, "status": "pending"}]

        def route(table_name):
            mock_tbl = MagicMock()
            if table_name == "offices":
                mock_tbl.select.return_value.eq.return_value.execute.return_value = mock_office_res
            elif table_name == "submissions":
                mock_tbl.insert.return_value.execute.return_value = mock_sub_res
            elif table_name == "tasks":
                mock_tbl.insert.return_value.execute.return_value = MagicMock()
            elif table_name == "ai_processing_queue":
                mock_tbl.insert.return_value.execute.return_value = mock_queue_res
            return mock_tbl

        mock_db.table.side_effect = route
        return mock_db

    def _payload(self, month: int = 5, submission_id: int = 77) -> dict:
        return {
            "office_name": "مكتب الشؤون الطلابية",
            "submitter_name": "محمد علي",
            "month": month,
            "year": 2026,
            "has_plan": False,
            "tasks": [
                {
                    "manager_name": "محمد علي",
                    "task_name": "متابعة الطلاب",
                    "task_type": "ضمن الخطة الشهرية",
                    "task_status": "مكتملة",
                }
            ],
        }

    @patch("routes.submissions.get_supabase_client")
    def test_endpoint_inserts_queue_row(self, mock_get_client, client):
        """يتحقق من إدراج صف في ai_processing_queue بعد حفظ submission وtasks."""
        mock_db = self._make_db_mock()
        mock_get_client.return_value = mock_db

        with patch("web_server._background_pipeline_runner") as mock_runner:
            resp = client.post("/api/submit-report", json=self._payload())
            assert resp.status_code == 200
            # مسار المعالجة لا يُستدعى مباشرة
            mock_runner.assert_not_called()

        # الطابور يجب أن يُستدعى
        queue_calls = [c for c in mock_db.table.call_args_list
                       if c.args and c.args[0] == "ai_processing_queue"]
        assert len(queue_calls) == 1

    @patch("routes.submissions.get_supabase_client")
    def test_endpoint_response_mentions_processing(self, mock_get_client, client):
        """يتحقق من أن الاستجابة تفيد بأن التقرير قيد المعالجة."""
        mock_db = self._make_db_mock()
        mock_get_client.return_value = mock_db

        resp = client.post("/api/submit-report", json=self._payload(month=8))
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        # الرسالة تشير للمعالجة الغير متزامنة (لا تقول "بدأت المعالجة فوراً")
        assert "قيد المعالجة" in data["message"]

    @patch("routes.submissions.get_supabase_client")
    def test_endpoint_queue_insert_failure_does_not_break_response(self, mock_get_client, client):
        """
        حتى لو فشل إدراج صف الطابور، يجب أن يُعاد submission_id للمستخدم
        (الإدراج في الطابور لا يُلغي حفظ التقرير).
        """
        mock_db = MagicMock()

        mock_office_res = MagicMock()
        mock_office_res.data = [{"id": 3}]
        mock_sub_res = MagicMock()
        mock_sub_res.data = [{"id": 88}]

        def route(table_name):
            mock_tbl = MagicMock()
            if table_name == "offices":
                mock_tbl.select.return_value.eq.return_value.execute.return_value = mock_office_res
            elif table_name == "submissions":
                mock_tbl.insert.return_value.execute.return_value = mock_sub_res
            elif table_name == "tasks":
                mock_tbl.insert.return_value.execute.return_value = MagicMock()
            elif table_name == "ai_processing_queue":
                # محاكاة فشل الإدراج في الطابور
                mock_tbl.insert.return_value.execute.side_effect = Exception("Queue DB error")
            return mock_tbl

        mock_db.table.side_effect = route
        mock_get_client.return_value = mock_db

        resp = client.post("/api/submit-report", json=self._payload(month=9))
        # يجب أن تبقى الاستجابة ناجحة (200) رغم فشل الطابور
        assert resp.status_code == 200
        assert resp.json()["submission_id"] == 88


# ─── 6. اختبار claim_row الذري ───────────────────────────────────────────────

class TestClaimRow:
    """يتحقق من السلوك الذري لـ claim_row."""

    def test_claim_row_returns_true_on_success(self):
        """يُعيد True عندما يجد الصف بحالة pending وينجح في التحديث."""
        from worker import claim_row

        db = MagicMock()
        db.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(data=[{"id": 1}])

        result = claim_row(db, queue_id=1)
        assert result is True

    def test_claim_row_returns_false_when_already_claimed(self):
        """يُعيد False عند عدم وجود الصف (تحوّل بالفعل من قِبل instance آخر)."""
        from worker import claim_row

        db = MagicMock()
        # الصف لم يُعدَّل (data فارغة — الشرط الذري لم يتحقق)
        db.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(data=[])

        result = claim_row(db, queue_id=99)
        assert result is False


# ─── 7. صمام الأمان: الانتظار مضمون في run_worker() بعد أي معالجة ─────────────

class TestCooldownGuarantee:
    """
    يتحقق من أن run_worker() يستدعي _interruptible_sleep بالمدة الصحيحة
    بعد كل معالجة — سواء كانت ناجحة، فشلاً مؤقتاً، أو فشلاً نهائياً.
    هذا هو صمام الأمان الفعلي ضد rate limit.
    """

    def _make_db_mock(self):
        """mock للـ DB يُعيد صفاً واحداً ثم يطلب الإيقاف."""
        db = MagicMock()
        db.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(data=[{"id": 1}])
        db.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
        return db

    @patch("worker._shutdown_requested", False)
    @patch("worker._background_pipeline_runner")
    def test_cooldown_applied_after_success(self, mock_runner):
        """
        بعد النجاح، run_worker() يجب أن يستدعي _interruptible_sleep
        بمقدار QUEUE_MIN_DELAY_SECONDS قبل التقاط الصف التالي.
        """
        import worker as wmod

        db = self._make_db_mock()
        mock_runner.return_value = None
        row = _make_queue_row(queue_id=10, submission_id=50, attempts=0)

        sleep_calls = []

        def fake_sleep(seconds):
            sleep_calls.append(seconds)
            # بعد أول نوم، أوقف الحلقة
            wmod._shutdown_requested = True

        with patch("worker.get_supabase_client", return_value=db), \
             patch("worker.recover_stuck_rows"), \
             patch("worker.fetch_next_pending", return_value=row), \
             patch("worker._interruptible_sleep", side_effect=fake_sleep):

            wmod._shutdown_requested = False
            wmod.run_worker()

        # يجب أن يكون أول استدعاء للـ sleep بمقدار QUEUE_MIN_DELAY_SECONDS
        assert len(sleep_calls) >= 1
        assert sleep_calls[0] == cfg.QUEUE_MIN_DELAY_SECONDS

    @patch("worker._background_pipeline_runner")
    def test_cooldown_applied_after_retry(self, mock_runner):
        """
        بعد فشل مؤقت (retry)، run_worker() يجب أن يستدعي _interruptible_sleep
        بمقدار backoff_delay = QUEUE_MIN_DELAY_SECONDS * BACKOFF ** attempts.
        يُثبت أن الانتظار يحدث حتى لو process_one أعادت قيمة أكبر من min_delay.
        """
        import worker as wmod

        db = self._make_db_mock()
        mock_runner.side_effect = RuntimeError("transient error")
        row = _make_queue_row(queue_id=11, submission_id=51, attempts=0)

        sleep_calls = []

        def fake_sleep(seconds):
            sleep_calls.append(seconds)
            wmod._shutdown_requested = True

        with patch("worker.get_supabase_client", return_value=db), \
             patch("worker.recover_stuck_rows"), \
             patch("worker.fetch_next_pending", return_value=row), \
             patch("worker.mark_retry"), \
             patch("worker._interruptible_sleep", side_effect=fake_sleep):

            wmod._shutdown_requested = False
            wmod.run_worker()

        expected_backoff = cfg.QUEUE_MIN_DELAY_SECONDS * (cfg.QUEUE_BACKOFF_MULTIPLIER ** 1)
        assert len(sleep_calls) >= 1
        # الانتظار يجب أن يكون بمقدار الـ backoff (أكبر من min_delay)
        assert sleep_calls[0] == expected_backoff

    @patch("worker._background_pipeline_runner")
    def test_cooldown_applied_after_final_failure(self, mock_runner):
        """
        بعد الفشل النهائي (max_attempts)، run_worker() يجب أن يستدعي
        _interruptible_sleep بمقدار QUEUE_MIN_DELAY_SECONDS على الأقل.
        """
        import worker as wmod

        db = self._make_db_mock()
        mock_runner.side_effect = Exception("fatal")
        row = _make_queue_row(
            queue_id=12,
            submission_id=52,
            attempts=cfg.QUEUE_MAX_ATTEMPTS - 1
        )

        sleep_calls = []

        def fake_sleep(seconds):
            sleep_calls.append(seconds)
            wmod._shutdown_requested = True

        with patch("worker.get_supabase_client", return_value=db), \
             patch("worker.recover_stuck_rows"), \
             patch("worker.fetch_next_pending", return_value=row), \
             patch("worker.mark_failed_final"), \
             patch("worker._interruptible_sleep", side_effect=fake_sleep):

            wmod._shutdown_requested = False
            wmod.run_worker()

        assert len(sleep_calls) >= 1
        assert sleep_calls[0] == cfg.QUEUE_MIN_DELAY_SECONDS
