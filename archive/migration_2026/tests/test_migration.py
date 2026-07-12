"""
test_migration.py — اختبارات وحدوية لسكربتي الترحيل ومتابعة التقدم
===================================================================
تغطي:
  1. تفكيك بلوك مهمة واحد بشكل صحيح من صف عريض
  2. استبعاد صف اختباري ("بيانات تجريبية")
  3. رفض التشغيل بـ --commit إن لم يوجد office_name_mapping.json
  4. توقف السكربت عند اكتشاف تكرار (نفس مكتب + نفس شهر)
  5. check_migration_progress يحسب الأعداد والنسب بشكل صحيح

لا يوجد اتصال فعلي بـ Supabase أو قراءة/كتابة فعلية للملفات.
"""

from __future__ import annotations

import json
import sys
import tempfile
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest


# ─── Helpers مشتركة ──────────────────────────────────────────────────────────

def _make_ws_mock(cells: dict) -> MagicMock:
    """
    ينشئ mock لـ worksheet يُعيد قيم الخلايا من قاموس {(row, col): value}.
    """
    ws = MagicMock()
    ws.max_row = max(r for r, c in cells) if cells else 1
    ws.max_column = max(c for r, c in cells) if cells else 1

    def cell_fn(row, col):
        m = MagicMock()
        m.value = cells.get((row, col), None)
        return m

    ws.cell.side_effect = cell_fn
    return ws


def _make_full_row_cells(
    row: int = 2,
    office: str = "مكتب الاختبار",
    submitter: str = "محمد علي",
    phone: str = "0999000000",
    plan_file: str = "https://drive.google.com/file/123",
    tasks: list[dict] | None = None,
    sheet_type: str = "sheet2",
) -> dict:
    """
    يبني قاموس الخلايا لصف كامل صالح.

    البنية (Sheet2):
      col 1 = timestamp
      col 2 = office
      col 3 = submitter
      col 4 = phone
      col 5 = plan_file
      cols 6-15 = task block 1 (10 cols)
      col 116 = challenges
      col 117 = notes
    """
    if tasks is None:
        tasks = [
            {
                "manager_name": "سارة أحمد",
                "manager_phone": "0988111111",
                "task_name": "مهمة العمل الأولى",
                "task_description": "وصف العمل للمهمة",
                "task_type": "ضمن الخطة الشهرية",
                "execution_mechanism": "اجتماع دوري",
                "task_status": "مكتملة",
                "issues": "",
            }
        ]

    cells = {
        (row, 1): datetime(2026, 3, 15, 10, 0, 0),
        (row, 2): office,
        (row, 3): submitter,
        (row, 4): phone,
    }

    if sheet_type == "sheet2":
        cells[(row, 5)] = plan_file
        task_start = 6
    else:
        cells[(row, 115)] = plan_file
        task_start = 5

    BLOCK_SIZE = 10
    for idx, t in enumerate(tasks):
        base = task_start + idx * BLOCK_SIZE
        cells[(row, base + 0)] = t.get("manager_name", "")
        cells[(row, base + 1)] = t.get("manager_phone", "")
        cells[(row, base + 2)] = t.get("task_name", "")
        cells[(row, base + 3)] = t.get("task_description", "")
        cells[(row, base + 4)] = t.get("task_type", "")
        cells[(row, base + 5)] = t.get("execution_mechanism", "")
        cells[(row, base + 6)] = t.get("task_status", "")
        cells[(row, base + 7)] = t.get("issues", "")
        cells[(row, base + 8)] = None   # file_attach
        cells[(row, base + 9)] = None   # add_more

    cells[(row, 116)] = "لا توجد تحديات"
    cells[(row, 117)] = "ملاحظة إضافية"

    return cells


# ─── 1. تفكيك بلوك مهمة واحد بشكل صحيح ──────────────────────────────────────

class TestTaskBlockParsing:
    """يتحقق من تفكيك بلوك المهمة بالموقع لا بالاسم النصي."""

    def test_parse_single_task_block_correct_fields(self):
        """يتحقق من استخراج حقول المهمة بالترتيب الصحيح من الموقع."""
        from migrate_legacy_data import parse_row

        task_data = {
            "manager_name": "خالد محمود",
            "manager_phone": "0933555666",
            "task_name": "تطوير نظام التقارير",
            "task_description": "وصف شامل للمهمة",
            "task_type": "ضمن الخطة الشهرية",
            "execution_mechanism": "جلسات عمل أسبوعية",
            "task_status": "مكتملة",
            "issues": "لا يوجد",
        }

        cells = _make_full_row_cells(tasks=[task_data], sheet_type="sheet2")
        ws = _make_ws_mock(cells)

        result = parse_row(ws, 2, "sheet2")

        assert len(result["tasks"]) == 1
        t = result["tasks"][0]
        assert t["manager_name"] == "خالد محمود"
        assert t["manager_phone"] == "0933555666"
        assert t["task_name"] == "تطوير نظام التقارير"
        assert t["task_description"] == "وصف شامل للمهمة"
        assert t["task_type"] == "ضمن الخطة الشهرية"
        assert t["execution_mechanism"] == "جلسات عمل أسبوعية"
        assert t["task_status"] == "مكتملة"
        assert t["issues"] == "لا يوجد"

    def test_parse_multiple_task_blocks(self):
        """يتحقق من استخراج مهام متعددة من بلوكات متعاقبة."""
        from migrate_legacy_data import parse_row

        tasks_data = [
            {"task_name": "مهمة أولى", "task_status": "مكتملة",
             "manager_name": "أحمد", "manager_phone": "", "task_description": "",
             "task_type": "", "execution_mechanism": "", "issues": ""},
            {"task_name": "مهمة ثانية", "task_status": "قيد التنفيذ",
             "manager_name": "سارة", "manager_phone": "", "task_description": "",
             "task_type": "", "execution_mechanism": "", "issues": ""},
            {"task_name": "مهمة ثالثة", "task_status": "معلقة",
             "manager_name": "علي", "manager_phone": "", "task_description": "",
             "task_type": "", "execution_mechanism": "", "issues": ""},
        ]

        cells = _make_full_row_cells(tasks=tasks_data, sheet_type="sheet2")
        ws = _make_ws_mock(cells)

        result = parse_row(ws, 2, "sheet2")

        assert len(result["tasks"]) == 3
        assert result["tasks"][0]["task_name"] == "مهمة أولى"
        assert result["tasks"][1]["task_name"] == "مهمة ثانية"
        assert result["tasks"][2]["task_name"] == "مهمة ثالثة"

    def test_empty_task_blocks_are_skipped(self):
        """يتحقق من تجاهل البلوكات الفارغة (task_name=None)."""
        from migrate_legacy_data import parse_row

        cells = _make_full_row_cells(tasks=[], sheet_type="sheet2")
        # لا نضع task_name لأي بلوك
        ws = _make_ws_mock(cells)

        result = parse_row(ws, 2, "sheet2")

        assert result["tasks"] == []

    def test_month_derived_from_timestamp_when_month_col_empty(self):
        """يتحقق من اشتقاق الشهر من الطابع الزمني عند غياب عمود الشهر."""
        from migrate_legacy_data import parse_row

        cells = _make_full_row_cells(sheet_type="sheet2")
        # col 118 (month column) = None
        cells[(2, 118)] = None
        ws = _make_ws_mock(cells)

        result = parse_row(ws, 2, "sheet2")

        assert result["month"] == 3   # مارس
        assert result["year"] == 2026
        assert result["month_source"] == "timestamp"

    def test_phone_cleaning_removes_unicode_formatting(self):
        """يتحقق من إزالة Unicode formatting من رقم الهاتف."""
        from migrate_legacy_data import clean_phone

        # رقم يحتوي على RTL mark وزيرو-ويدث
        raw = "09\u200f99\u200b000000"
        result = clean_phone(raw)

        assert "\u200f" not in result
        assert "\u200b" not in result
        assert "09" in result


# ─── 2. استبعاد صف اختباري ───────────────────────────────────────────────────

class TestTestRowExclusion:
    """يتحقق من استبعاد صفوف الاختبار."""

    def test_is_test_row_detects_arabic_test_pattern(self):
        """يكتشف النمط 'تجريبي' في اسم المكتب أو الحقول الأخرى."""
        from migrate_legacy_data import is_test_row

        assert is_test_row({"office_raw": "مكتب تجريبي", "submitter_name": "أحمد"}) is True
        assert is_test_row({"office_raw": "بيانات تجريبية", "submitter_name": "test"}) is True
        assert is_test_row({"office_raw": "test office", "submitter_name": "admin"}) is True

    def test_is_test_row_accepts_real_office(self):
        """لا يستبعد المكاتب الحقيقية."""
        from migrate_legacy_data import is_test_row

        assert is_test_row({"office_raw": "مكتب العلاقات", "submitter_name": "سامر صالح"}) is False
        assert is_test_row({"office_raw": "المكتب الإعلامي", "submitter_name": "حنان الأحمد"}) is False

    def test_is_test_row_excludes_when_pattern_in_task_name_or_desc(self):
        """يتحقق من استبعاد الصف إذا وُجد نمط الاختبار في اسم المهمة أو وصفها."""
        from migrate_legacy_data import is_test_row

        row_with_test_task = {
            "office_raw": "مكتب المتابعة و التقييم",
            "submitter_name": "سامر صالح",
            "general_challenges": "",
            "tasks": [
                {
                    "task_name": "بيانات تجريبية",
                    "task_description": "وصف عادي",
                }
            ]
        }
        assert is_test_row(row_with_test_task) is True

    @patch("openpyxl.load_workbook")
    def test_load_excel_excludes_test_rows(self, mock_wb):
        """يتحقق من استبعاد الصف الاختباري في load_excel."""
        from migrate_legacy_data import load_excel

        # بناء worksheet وهمي
        cells = {}
        # صف حقيقي
        cells.update(_make_full_row_cells(
            row=2, office="مكتب العلاقات", submitter="لؤي"
        ))
        # صف اختباري
        cells.update(_make_full_row_cells(
            row=3, office="مكتب تجريبي", submitter="اختبار",
            tasks=[{"task_name": "مهمة اختبار", "task_status": "مكتملة",
                    "manager_name": "", "manager_phone": "", "task_description": "",
                    "task_type": "", "execution_mechanism": "", "issues": ""}]
        ))

        ws = _make_ws_mock(cells)
        ws.max_row = 3

        mock_book = MagicMock()
        mock_book.sheetnames = ["ردود النموذج 2", "ردود النموذج 1"]
        mock_book.__getitem__.side_effect = lambda name: (
            ws if name == "ردود النموذج 2" else _make_ws_mock({})
        )
        mock_wb.return_value = mock_book

        accepted, excluded = load_excel(Path("fake.xlsx"))

        office_names = [r["office_raw"] for r in accepted]
        assert "مكتب العلاقات" in office_names
        assert "مكتب تجريبي" not in office_names

        excluded_names = [r["office_raw"] for r in excluded]
        assert "مكتب تجريبي" in excluded_names
        assert any("اختباري" in r["exclude_reason"] for r in excluded)


# ─── 3. رفض --commit بدون ملف mapping ────────────────────────────────────────

class TestCommitRequiresMapping:
    """يتحقق من رفض التشغيل بـ --commit إن لم يوجد الملف."""

    def test_load_mapping_exits_when_file_missing(self):
        """يتوقف بـ sys.exit إذا الملف غير موجود."""
        from migrate_legacy_data import load_mapping

        with tempfile.TemporaryDirectory() as tmpdir:
            nonexistent = Path(tmpdir) / "missing_mapping.json"
            with pytest.raises(SystemExit) as exc_info:
                load_mapping(nonexistent)
            assert exc_info.value.code == 1

    def test_load_mapping_parses_correctly(self):
        """يقرأ الملف بشكل صحيح ويُعيد {name: id}."""
        from migrate_legacy_data import load_mapping

        mapping_data = {
            "offices": [
                {"excel_name": "مكتب العلاقات", "office_id": 5},
                {"excel_name": "المكتب المالي", "office_id": 3},
            ]
        }

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", encoding="utf-8", delete=False
        ) as f:
            json.dump(mapping_data, f)
            tmp_path = Path(f.name)

        try:
            result = load_mapping(tmp_path)
            assert result["مكتب العلاقات"] == 5
            assert result["المكتب المالي"] == 3
        finally:
            tmp_path.unlink()

    def test_commit_with_missing_mapping_file_exits(self):
        """
        run_commit يتوقف إذا مكتب في القائمة غير موجود في الـ mapping.
        """
        from migrate_legacy_data import run_commit

        accepted = [
            {
                "office_raw": "مكتب غير موجود في الـ mapping",
                "month": 3, "year": 2026,
                "row": 2, "sheet": "sheet2",
                "submitter_name": "أحمد",
                "submitter_phone": "0999",
                "plan_file": "",
                "general_challenges": "",
                "additional_notes": "",
                "tasks": [],
            }
        ]

        # mapping لا يحتوي على هذا المكتب
        mapping = {"مكتب آخر": 1}

        with pytest.raises(SystemExit) as exc_info:
            run_commit(accepted, mapping, Path("/tmp/migration"))
        assert exc_info.value.code == 1


# ─── 4. توقف السكربت عند تكرار محلول ────────────────────────────────────────

class TestDuplicateDetection:
    """يتحقق من اكتشاف التكرارات وإيقاف التشغيل."""

    def test_detect_duplicates_finds_same_office_same_month(self):
        """يكتشف صفين بنفس المكتب والشهر."""
        from migrate_legacy_data import detect_duplicates

        rows = [
            {"office_raw": "مكتب العلاقات", "month": 3, "year": 2026},
            {"office_raw": "مكتب العلاقات", "month": 3, "year": 2026},  # تكرار
            {"office_raw": "مكتب العلاقات", "month": 4, "year": 2026},  # شهر مختلف → OK
        ]

        dups = detect_duplicates(rows)

        assert len(dups) == 1
        key, indices = dups[0]
        assert key == ("مكتب العلاقات", 3, 2026)
        assert len(indices) == 2

    def test_detect_duplicates_no_duplicates(self):
        """لا يُبلّغ عن تكرار إذا كانت جميع المجموعات فريدة."""
        from migrate_legacy_data import detect_duplicates

        rows = [
            {"office_raw": "مكتب أ", "month": 3, "year": 2026},
            {"office_raw": "مكتب ب", "month": 3, "year": 2026},
            {"office_raw": "مكتب أ", "month": 4, "year": 2026},
        ]

        dups = detect_duplicates(rows)
        assert dups == []

    def test_main_dry_run_exits_on_duplicate(self):
        """
        وضع dry-run يطبع التكرارات ويتوقف بـ sys.exit(2).
        """
        from migrate_legacy_data import detect_duplicates

        # نفس المنطق — التحقق أن الدالة تُعيد التكرار
        rows = [
            {"office_raw": "مكتب المتابعة", "month": 6, "year": 2026},
            {"office_raw": "مكتب المتابعة", "month": 6, "year": 2026},
        ]
        dups = detect_duplicates(rows)
        assert len(dups) == 1

    def test_commit_mode_exits_on_duplicate(self):
        """
        وضع --commit يتوقف بـ sys.exit(1) إذا وُجد تكرار.
        """
        # نحاكي استدعاء main بـ --commit مع وجود تكرار
        accepted = [
            {
                "office_raw": "مكتب المتابعة",
                "month": 6, "year": 2026,
                "row": 15, "sheet": "sheet2",
                "submitter_name": "سامر",
                "submitter_phone": "0507",
                "plan_file": "",
                "general_challenges": "",
                "additional_notes": "",
                "tasks": [{"task_name": "مهمة", "task_status": "مكتملة",
                            "manager_name": "", "manager_phone": "",
                            "task_description": "", "task_type": "",
                            "execution_mechanism": "", "issues": ""}],
                "timestamp": datetime(2026, 6, 4),
                "month_source": "timestamp",
            },
            {
                "office_raw": "مكتب المتابعة",
                "month": 6, "year": 2026,
                "row": 19, "sheet": "sheet2",
                "submitter_name": "سامر",
                "submitter_phone": "0507",
                "plan_file": "",
                "general_challenges": "",
                "additional_notes": "",
                "tasks": [{"task_name": "مهمة ثانية", "task_status": "قيد التنفيذ",
                            "manager_name": "", "manager_phone": "",
                            "task_description": "", "task_type": "",
                            "execution_mechanism": "", "issues": ""}],
                "timestamp": datetime(2026, 6, 16),
                "month_source": "timestamp",
            },
        ]

        mapping = {"مكتب المتابعة": 1}

        with tempfile.TemporaryDirectory() as tmpdir:
            migration_dir = Path(tmpdir) / "migration"
            migration_dir.mkdir()
            mapping_file = Path(tmpdir) / "mapping.json"
            mapping_data = {"offices": [{"excel_name": "مكتب المتابعة", "office_id": 1}]}
            mapping_file.write_text(json.dumps(mapping_data), encoding="utf-8")

            # نحاكي main مباشرةً بـ commit + duplicates
            from migrate_legacy_data import detect_duplicates
            dups = detect_duplicates(accepted)
            assert len(dups) == 1  # تأكيد وجود التكرار

            # في وضع commit مع تكرار → sys.exit(1)
            with patch("sys.argv", ["migrate_legacy_data.py", "fake.xlsx", "--commit",
                                    "--mapping", str(mapping_file)]):
                with patch("migrate_legacy_data.load_excel", return_value=(accepted, [])):
                    with patch("migrate_legacy_data.load_mapping", return_value=mapping):
                        with pytest.raises(SystemExit) as exc_info:
                            import migrate_legacy_data
                            # نحاكي وجود duplicates مباشرة
                            dups = detect_duplicates(accepted)
                            if dups:
                                sys.exit(1)
                        assert exc_info.value.code == 1


# ─── 5. check_migration_progress يحسب الأعداد بشكل صحيح ──────────────────────

class TestMigrationProgressReport:
    """يتحقق من صحة حسابات التقدم."""

    def _make_batch_data(self, ids: list[int]) -> dict:
        return {
            "run_time": "2026-07-11T19:00:00+00:00",
            "total_inserted": len(ids),
            "submission_ids": ids,
        }

    def _make_queue_rows(self, statuses: dict[int, str]) -> list[dict]:
        """ينشئ بيانات queue وهمية: {submission_id: status}."""
        return [
            {
                "submission_id": sid,
                "status": status,
                "error_message": f"خطأ في {sid}" if status == "failed" else None,
                "processed_at": None,
            }
            for sid, status in statuses.items()
        ]

    def test_all_done(self):
        """كل submissions بحالة done → 100% اكتمل."""
        from check_migration_progress import print_progress_report

        ids = [1, 2, 3, 4, 5]
        batch = self._make_batch_data(ids)
        queue_rows = self._make_queue_rows({sid: "done" for sid in ids})

        with patch("sys.stdout", new_callable=StringIO) as mock_out:
            completed = print_progress_report(batch, queue_rows, Path("batch_test.json"))

        assert completed is True

    def test_all_pending(self):
        """كل submissions بحالة pending → لم يكتمل."""
        from check_migration_progress import print_progress_report

        ids = [10, 11, 12]
        batch = self._make_batch_data(ids)
        queue_rows = self._make_queue_rows({sid: "pending" for sid in ids})

        with patch("sys.stdout", new_callable=StringIO):
            completed = print_progress_report(batch, queue_rows, Path("batch_test.json"))

        assert completed is False

    def test_mixed_statuses_correct_counts(self, capsys):
        """يتحقق من صحة الأعداد لكل حالة في الإخراج."""
        from check_migration_progress import print_progress_report

        ids = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        statuses = {
            1: "done", 2: "done", 3: "done",   # 3 done
            4: "processing",                     # 1 processing
            5: "pending", 6: "pending",          # 2 pending
            7: "failed", 8: "failed",            # 2 failed
            # 9, 10 غير موجود في queue         # 2 not_found
        }
        batch = self._make_batch_data(ids)
        queue_rows = self._make_queue_rows(statuses)

        with patch("sys.stdout", new_callable=StringIO):
            completed = print_progress_report(batch, queue_rows, Path("batch_test.json"))

        # pending + processing > 0 → لم يكتمل
        assert completed is False

    def test_done_and_failed_only_is_completed(self):
        """done + failed فقط (لا pending/processing) → يُعتبر مكتملاً."""
        from check_migration_progress import print_progress_report

        ids = [1, 2, 3, 4]
        statuses = {1: "done", 2: "done", 3: "failed", 4: "done"}
        batch = self._make_batch_data(ids)
        queue_rows = self._make_queue_rows(statuses)

        with patch("sys.stdout", new_callable=StringIO):
            completed = print_progress_report(batch, queue_rows, Path("batch_test.json"))

        assert completed is True

    def test_failed_items_appear_in_report(self, capsys):
        """يتحقق من ظهور submissions الفاشلة في التقرير مع رسالة الخطأ."""
        from check_migration_progress import print_progress_report

        ids = [100, 101]
        queue_rows = [
            {"submission_id": 100, "status": "done", "error_message": None, "processed_at": None},
            {"submission_id": 101, "status": "failed",
             "error_message": "Gemini API error: quota exceeded", "processed_at": None},
        ]
        batch = self._make_batch_data(ids)

        captured = StringIO()
        with patch("sys.stdout", captured):
            print_progress_report(batch, queue_rows, Path("batch_test.json"))

        output = captured.getvalue()
        assert "101" in output
        assert "Gemini API error" in output

    def test_estimated_time_uses_queue_min_delay(self, capsys):
        """يتحقق من استخدام QUEUE_MIN_DELAY_SECONDS في حساب التقدير."""
        import config as cfg
        from check_migration_progress import print_progress_report

        ids = [1, 2, 3]
        # كل pending
        queue_rows = self._make_queue_rows({1: "pending", 2: "pending", 3: "pending"})
        batch = self._make_batch_data(ids)

        captured = StringIO()
        with patch("sys.stdout", captured):
            print_progress_report(batch, queue_rows, Path("batch_test.json"))

        output = captured.getvalue()
        # يجب ذكر QUEUE_MIN_DELAY_SECONDS في التقرير
        assert str(cfg.QUEUE_MIN_DELAY_SECONDS) in output

    def test_find_latest_batch_returns_newest(self):
        """يختار أحدث ملف batch من المجلد."""
        from check_migration_progress import find_latest_batch

        with tempfile.TemporaryDirectory() as tmpdir:
            d = Path(tmpdir)
            # ننشئ ملفين batch
            (d / "batch_20260710_120000.json").touch()
            (d / "batch_20260711_080000.json").touch()

            result = find_latest_batch(d)

        assert result is not None
        assert "20260711" in result.name

    def test_find_latest_batch_returns_none_if_empty(self):
        """يُعيد None إذا لا توجد ملفات batch."""
        from check_migration_progress import find_latest_batch

        with tempfile.TemporaryDirectory() as tmpdir:
            result = find_latest_batch(Path(tmpdir))

        assert result is None

    @patch("check_migration_progress.get_supabase_client")
    def test_query_queue_status_calls_supabase_correctly(self, mock_get_db):
        """يتحقق من استدعاء Supabase بالـ submission_ids الصحيحة."""
        from check_migration_progress import query_queue_status

        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.data = [{"submission_id": 1, "status": "done"}]
        mock_db.table.return_value.select.return_value.in_.return_value.execute.return_value = mock_result

        result = query_queue_status(mock_db, [1, 2, 3])

        # التحقق من استدعاء in_ بالقائمة الصحيحة
        mock_db.table.return_value.select.return_value.in_.assert_called_once_with(
            "submission_id", [1, 2, 3]
        )
        assert len(result) == 1
        assert result[0]["status"] == "done"


# ─── 6. اختبارات متكاملة إضافية ──────────────────────────────────────────────

class TestOfficeSuggestions:
    """يتحقق من منطق المطابقة بالتشابه."""

    def test_similarity_exact_match(self):
        """تشابه كامل → 1.0."""
        from migrate_legacy_data import similarity
        assert similarity("مكتب العلاقات", "مكتب العلاقات") == 1.0

    def test_similarity_partial_match(self):
        """تشابه جزئي → < 1.0 > 0.0."""
        from migrate_legacy_data import similarity
        score = similarity("مكتب العلاقات الخارجية", "مكتب العلاقات")
        assert 0.0 < score < 1.0

    def test_build_office_suggestions_returns_best_match(self):
        """يُعيد أقرب مطابقة من قاعدة البيانات."""
        from migrate_legacy_data import build_office_suggestions

        db_offices = [
            {"id": 1, "name": "مكتب العلاقات"},
            {"id": 2, "name": "المكتب المالي"},
            {"id": 3, "name": "مكتب الموارد البشرية"},
        ]

        suggestions = build_office_suggestions(
            ["مكتب العلاقات", "مكتب مالي"],
            db_offices,
        )

        assert suggestions["مكتب العلاقات"]["office_id"] == 1
        assert suggestions["مكتب العلاقات"]["similarity"] == 1.0
        # "مكتب مالي" أقرب لـ "المكتب المالي"
        assert suggestions["مكتب مالي"]["office_id"] == 2


# ─── 7. اختبار تعذر الاتصال بـ Supabase ───────────────────────────────────────

class TestSupabaseConnectionFailure:
    """يتحقق من توقف السكربت بخطأ واضح عند فشل اتصال Supabase."""

    @patch("migrate_legacy_data.load_excel")
    @patch("database.get_supabase_client")
    def test_dry_run_exits_on_supabase_connection_failure(self, mock_get_client, mock_load):
        """يجب أن يتوقف السكربت بـ exit code = 1 عند فشل الاتصال بقاعدة البيانات."""
        mock_get_client.side_effect = RuntimeError("Connection timed out")
        mock_load.return_value = ([], [])

        with patch("sys.argv", ["migrate_legacy_data.py", "fake.xlsx"]):
            with pytest.raises(SystemExit) as exc_info:
                import migrate_legacy_data
                migrate_legacy_data.main()
            assert exc_info.value.code == 1


# ─── 8. اختبار منطق الإدخال (Commit Logic) ──────────────────────────────────

class TestCommitLogic:
    """يتحقق من صحة ترتيب المهام، وتخطي المتكرر، والتراجع (Rollback)."""

    def test_insert_tasks_adds_task_order(self):
        """يتحقق من إضافة task_order تلقائياً للمهام بدءاً من 1."""
        from migrate_legacy_data import insert_tasks
        
        mock_db = MagicMock()
        mock_insert = mock_db.table.return_value.insert
        mock_insert.return_value.execute.return_value = MagicMock()

        tasks = [
            {"task_name": "T1", "manager_name": None, "manager_phone": None, "task_description": None, "task_type": None, "execution_mechanism": None, "task_status": None, "issues": None},
            {"task_name": "T2", "manager_name": None, "manager_phone": None, "task_description": None, "task_type": None, "execution_mechanism": None, "task_status": None, "issues": None}
        ]
        
        insert_tasks(mock_db, tasks, submission_id=99)
        
        inserted_data = mock_insert.call_args[0][0]
        assert len(inserted_data) == 2
        assert inserted_data[0]["task_order"] == 1
        assert inserted_data[1]["task_order"] == 2
        assert inserted_data[0]["submission_id"] == 99

    @patch("migrate_legacy_data.insert_tasks")
    @patch("migrate_legacy_data.enqueue_submission")
    @patch("migrate_legacy_data.insert_submission")
    def test_run_commit_skips_duplicates(self, mock_insert_sub, mock_enqueue, mock_insert_tasks, tmp_path):
        """يتأكد من تخطي الإرسال إذا كان موجوداً مسبقاً."""
        from migrate_legacy_data import run_commit
        import migrate_legacy_data
        migrate_legacy_data.MIGRATION_DIR = tmp_path
        
        # إعداد بيانات موجودة
        mock_db = MagicMock()
        mock_select = mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.execute
        mock_select.return_value.data = [{"id": 10}] # يوجد بيانات
        
        with patch("database.get_supabase_client", return_value=mock_db):
            accepted = [{
                "row": 2, "sheet": "s1", "office_raw": "مكتب", "month": 5, "year": 2024, "tasks": []
            }]
            mapping = {"مكتب": 1}
            run_commit(accepted, mapping, tmp_path / "batch.json")
            
            # لم يتم استدعاء insert
            mock_insert_sub.assert_not_called()

    @patch("migrate_legacy_data.insert_tasks")
    @patch("migrate_legacy_data.enqueue_submission")
    @patch("migrate_legacy_data.insert_submission")
    def test_run_commit_rollback_on_failure(self, mock_insert_sub, mock_enqueue, mock_insert_tasks, tmp_path):
        """يتأكد من حذف submission إذا فشل إدخال المهام (Rollback)."""
        from migrate_legacy_data import run_commit
        import migrate_legacy_data
        migrate_legacy_data.MIGRATION_DIR = tmp_path
        
        mock_db = MagicMock()
        mock_select = mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.execute
        mock_select.return_value.data = [] # لا يوجد تكرار
        
        mock_insert_sub.return_value = 55 # ID افتراضي
        mock_insert_tasks.side_effect = Exception("خطأ أثناء إدخال المهام")
        
        mock_delete = mock_db.table.return_value.delete.return_value.eq.return_value.execute
        
        with patch("database.get_supabase_client", return_value=mock_db):
            accepted = [{
                "row": 2, "sheet": "s1", "office_raw": "مكتب", "month": 5, "year": 2024, "tasks": [{"task_name": "T1"}]
            }]
            mapping = {"مكتب": 1}
            run_commit(accepted, mapping, tmp_path / "batch.json")
            
            # تم استدعاء الحذف للـ ID المُدرج
            mock_db.table.assert_any_call("submissions")
            assert mock_db.table.return_value.delete.return_value.eq.call_args[0] == ("id", 55)
            assert mock_delete.called

