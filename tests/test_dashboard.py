"""
test_dashboard.py — اختبارات وحدوية لـ endpoints لوحة التحكم
============================================================
تختبر الـ 4 endpoints الإدارية:
    GET    /api/submissions
    GET    /api/submissions/{id}
    PATCH  /api/submissions/{id}
    DELETE /api/submissions/{id}

تستخدم mock لـ Supabase لتجنب الاتصال الحقيقي بقاعدة البيانات.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch

from web_server import app
import config as cfg


@pytest.fixture
def client():
    """تهيئة عميل اختبار FastAPI."""
    return TestClient(app)


@pytest.fixture
def auth_client(client):
    """عميل اختبار مسجّل دخوله بـ JWT cookie."""
    response = client.post("/api/login", json={
        "username": cfg.GUSS_ADMIN_USERNAME,
        "password": cfg.GUSS_ADMIN_PASSWORD
    })
    assert response.status_code == 200
    return client


def _make_mock_db(submission_rows=None, task_rows=None):
    """
    يبني Mock لـ Supabase client يُعيد البيانات المطلوبة.
    submission_rows: قائمة صفوف submissions.
    task_rows: قائمة صفوف tasks.
    """
    mock_db = MagicMock()

    # Mock لـ submissions query
    sub_execute = MagicMock()
    sub_execute.data = submission_rows if submission_rows is not None else []

    # Mock لـ tasks query
    task_execute = MagicMock()
    task_execute.data = task_rows if task_rows is not None else []

    # نبني سلسلة الاستدعاءات الديناميكية
    mock_table = mock_db.table.return_value
    mock_table.select.return_value.eq.return_value.execute.return_value = sub_execute
    mock_table.select.return_value.eq.return_value.order.return_value.execute.return_value = task_execute
    mock_table.select.return_value.order.return_value.execute.return_value = sub_execute

    return mock_db


# ─── GET /api/submissions ─────────────────────────────────────────────────────

@patch("routes.dashboard.get_supabase_client")
def test_get_submissions_list_unauthorized(mock_get_db, client):
    """يرفض الوصول بدون JWT (401)."""
    response = client.get("/api/submissions")
    assert response.status_code == 401


@patch("routes.dashboard.get_supabase_client")
def test_get_submissions_list_success(mock_get_db, auth_client):
    """يُرجع قائمة التقارير بنجاح بدون فلترة."""
    mock_db = MagicMock()
    mock_get_db.return_value = mock_db

    # بناء الاستجابة المزيفة
    mock_result = MagicMock()
    mock_result.data = [
        {
            "id": 1,
            "submitter_name": "أحمد محمد",
            "month": 6,
            "year": 2026,
            "status": "processed",
            "created_at": "2026-06-21T10:00:00Z",
            "drive_report_link": "https://drive.google.com/file/d/abc/view",
            "offices": {"name": "مكتب حلب"},
        },
        {
            "id": 2,
            "submitter_name": "سامر علي",
            "month": 5,
            "year": 2026,
            "status": "pending",
            "created_at": "2026-06-01T08:00:00Z",
            "drive_report_link": None,
            "offices": {"name": "مكتب دمشق"},
        },
    ]

    (
        mock_db.table.return_value
        .select.return_value
        .order.return_value
        .execute.return_value
    ) = mock_result

    response = auth_client.get("/api/submissions")
    assert response.status_code == 200
    data = response.json()
    assert "submissions" in data
    assert data["total"] == 2
    assert data["submissions"][0]["office_name"] == "مكتب حلب"
    assert data["submissions"][1]["drive_report_link"] is None


@patch("routes.dashboard.get_supabase_client")
def test_get_submissions_list_with_filter(mock_get_db, auth_client):
    """يُطبّق الفلتر بـ status بشكل صحيح."""
    mock_db = MagicMock()
    mock_get_db.return_value = mock_db

    mock_result = MagicMock()
    mock_result.data = [
        {
            "id": 3,
            "submitter_name": "خالد حسن",
            "month": 4,
            "year": 2026,
            "status": "failed",
            "created_at": "2026-04-15T09:00:00Z",
            "drive_report_link": None,
            "offices": {"name": "مكتب اللاذقية"},
        }
    ]

    # بناء سلسلة تدعم eq → eq → order → execute
    chain = mock_db.table.return_value.select.return_value
    chain.eq.return_value.eq.return_value.order.return_value.execute.return_value = mock_result
    chain.eq.return_value.order.return_value.execute.return_value = mock_result
    chain.order.return_value.execute.return_value = mock_result

    response = auth_client.get("/api/submissions?status=failed")
    assert response.status_code == 200
    data = response.json()
    assert "submissions" in data


# ─── GET /api/submissions/{id} ────────────────────────────────────────────────

@patch("routes.dashboard.get_supabase_client")
def test_get_submission_detail_success(mock_get_db, auth_client):
    """يُرجع تفاصيل تقرير موجود مع مهامه."""
    mock_db = MagicMock()
    mock_get_db.return_value = mock_db

    sub_result = MagicMock()
    sub_result.data = [{
        "id": 1,
        "office_id": 5,
        "submitter_name": "أحمد محمد",
        "submitter_phone": "0912345678",
        "month": 6,
        "year": 2026,
        "has_plan": True,
        "plan_file_path": "20260601_abc.pdf",
        "general_challenges": "لا يوجد",
        "additional_notes": None,
        "status": "processed",
        "created_at": "2026-06-21T10:00:00Z",
        "drive_report_link": "https://drive.google.com/file/d/abc/view",
        "offices": {"name": "مكتب حلب"},
    }]

    task_result = MagicMock()
    task_result.data = [
        {
            "id": 10,
            "submission_id": 1,
            "task_order": 1,
            "manager_name": "سامر",
            "manager_phone": None,
            "task_name": "مهمة أولى",
            "task_description": None,
            "task_type": "ضمن الخطة الشهرية",
            "execution_mechanism": None,
            "task_status": "مكتملة",
            "issues": None,
            "created_at": "2026-06-21T10:01:00Z",
        }
    ]

    # سلسلة استدعاءات للـ submission
    mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value = sub_result
    # سلسلة للـ tasks (eq + order)
    mock_db.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value = task_result

    response = auth_client.get("/api/submissions/1")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 1
    assert data["office_name"] == "مكتب حلب"
    assert data["drive_report_link"] == "https://drive.google.com/file/d/abc/view"
    assert isinstance(data["tasks"], list)


@patch("routes.dashboard.get_supabase_client")
def test_get_submission_detail_not_found(mock_get_db, auth_client):
    """يُرجع 404 عند طلب تقرير غير موجود."""
    mock_db = MagicMock()
    mock_get_db.return_value = mock_db

    mock_result = MagicMock()
    mock_result.data = []
    mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_result

    response = auth_client.get("/api/submissions/9999")
    assert response.status_code == 404
    assert "غير موجود" in response.json()["detail"]


# ─── PATCH /api/submissions/{id} ─────────────────────────────────────────────

@patch("routes.dashboard.get_supabase_client")
def test_patch_submission_success(mock_get_db, auth_client):
    """يُعدّل حقولاً بسيطة بنجاح بدون استبدال مهام."""
    mock_db = MagicMock()
    mock_get_db.return_value = mock_db

    # التقرير موجود
    check_result = MagicMock()
    check_result.data = [{"id": 1}]
    mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value = check_result

    # update لا يحتاج return value خاص
    mock_db.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()

    payload = {
        "submitter_name": "أحمد علي",
        "general_challenges": "تحديات جديدة"
    }
    response = auth_client.patch("/api/submissions/1", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "success"


@patch("routes.dashboard.get_supabase_client")
def test_patch_submission_with_tasks(mock_get_db, auth_client):
    """يستبدل قائمة المهام بنجاح مع حذف القديمة وإدراج الجديدة."""
    mock_db = MagicMock()
    mock_get_db.return_value = mock_db

    check_result = MagicMock()
    check_result.data = [{"id": 1}]
    mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value = check_result
    mock_db.table.return_value.delete.return_value.eq.return_value.execute.return_value = MagicMock()
    mock_db.table.return_value.insert.return_value.execute.return_value = MagicMock()

    payload = {
        "tasks": [
            {
                "manager_name": "خالد",
                "task_name": "مهمة محدّثة",
                "task_type": "ضمن الخطة الشهرية",
                "task_status": "مكتملة"
            }
        ]
    }
    response = auth_client.patch("/api/submissions/1", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "success"


@patch("routes.dashboard.get_supabase_client")
def test_patch_submission_empty_tasks_rejected(mock_get_db, auth_client):
    """يرفض استبدال المهام بقائمة فارغة (400)."""
    mock_db = MagicMock()
    mock_get_db.return_value = mock_db

    check_result = MagicMock()
    check_result.data = [{"id": 1}]
    mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value = check_result

    payload = {"tasks": []}
    response = auth_client.patch("/api/submissions/1", json=payload)
    assert response.status_code == 400
    assert "مهمة واحدة على الأقل" in response.json()["detail"]


@patch("routes.dashboard.get_supabase_client")
def test_patch_submission_not_found(mock_get_db, auth_client):
    """يُرجع 404 عند تعديل تقرير غير موجود."""
    mock_db = MagicMock()
    mock_get_db.return_value = mock_db

    check_result = MagicMock()
    check_result.data = []
    mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value = check_result

    payload = {"submitter_name": "اسم جديد"}
    response = auth_client.patch("/api/submissions/9999", json=payload)
    assert response.status_code == 404


# ─── DELETE /api/submissions/{id} ────────────────────────────────────────────

@patch("routes.dashboard.get_supabase_client")
def test_delete_submission_success(mock_get_db, auth_client):
    """يحذف تقريراً بدون ملف خطة بنجاح."""
    mock_db = MagicMock()
    mock_get_db.return_value = mock_db

    check_result = MagicMock()
    check_result.data = [{"id": 1, "plan_file_path": None}]
    mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value = check_result
    mock_db.table.return_value.delete.return_value.eq.return_value.execute.return_value = MagicMock()

    response = auth_client.delete("/api/submissions/1")
    assert response.status_code == 200
    assert response.json()["status"] == "success"


@patch("routes.dashboard.get_supabase_client")
def test_delete_submission_with_plan_file(mock_get_db, auth_client):
    """يحذف تقريراً مع ملف خطة — يحذف الملف من Storage أيضاً."""
    mock_db = MagicMock()
    mock_get_db.return_value = mock_db

    check_result = MagicMock()
    check_result.data = [{"id": 2, "plan_file_path": "20260601_abc.pdf"}]
    mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value = check_result
    mock_db.table.return_value.delete.return_value.eq.return_value.execute.return_value = MagicMock()
    mock_db.storage.from_.return_value.remove.return_value = MagicMock()

    response = auth_client.delete("/api/submissions/2")
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    # التأكد من استدعاء حذف Storage
    mock_db.storage.from_.assert_called_once_with("monthly-plans")
    mock_db.storage.from_.return_value.remove.assert_called_once_with(["20260601_abc.pdf"])


@patch("routes.dashboard.get_supabase_client")
def test_delete_submission_storage_fail_continues(mock_get_db, auth_client):
    """فشل حذف ملف Storage لا يوقف حذف التقرير — يكمل بنجاح مع تحذير."""
    mock_db = MagicMock()
    mock_get_db.return_value = mock_db

    check_result = MagicMock()
    check_result.data = [{"id": 3, "plan_file_path": "20260601_xyz.pdf"}]
    mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value = check_result
    mock_db.table.return_value.delete.return_value.eq.return_value.execute.return_value = MagicMock()

    # محاكاة فشل حذف Storage
    mock_db.storage.from_.return_value.remove.side_effect = Exception("Storage error")

    response = auth_client.delete("/api/submissions/3")
    # يجب أن يكتمل الحذف بنجاح رغم فشل Storage
    assert response.status_code == 200
    assert response.json()["status"] == "success"


@patch("routes.dashboard.get_supabase_client")
def test_delete_submission_not_found(mock_get_db, auth_client):
    """يُرجع 404 عند حذف تقرير غير موجود."""
    mock_db = MagicMock()
    mock_get_db.return_value = mock_db

    check_result = MagicMock()
    check_result.data = []
    mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value = check_result

    response = auth_client.delete("/api/submissions/9999")
    assert response.status_code == 404
    assert "غير موجود" in response.json()["detail"]
