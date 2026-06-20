-- ============================================================================
-- GUSS — Migration 001: Create Tables
-- ============================================================================
-- جداول نظام التقارير الشهرية لمنظومة المتابعة الدورية
-- يُنفَّذ في Supabase SQL Editor
-- ============================================================================

-- ─── 1. جدول المكاتب ───────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS offices (
    id          SERIAL PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE offices IS 'المكاتب والأقسام المسجلة في المنظومة';
COMMENT ON COLUMN offices.name IS 'اسم المكتب — فريد وغير قابل للتكرار';


-- ─── 2. جدول التقارير المُقدَّمة ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS submissions (
    id                  SERIAL PRIMARY KEY,
    office_id           INTEGER NOT NULL
                        REFERENCES offices(id) ON DELETE RESTRICT,
    submitter_name      TEXT NOT NULL,
    submitter_phone     TEXT,
    month               INTEGER NOT NULL
                        CHECK (month BETWEEN 1 AND 12),
    year                INTEGER NOT NULL
                        CHECK (year BETWEEN 2020 AND 2100),
    has_plan            BOOLEAN NOT NULL DEFAULT FALSE,
    plan_file_path      TEXT,
    general_challenges  TEXT,
    additional_notes    TEXT,
    status              TEXT NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending', 'processed', 'failed')),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- منع تكرار التقرير لنفس المكتب والشهر والسنة
    UNIQUE (office_id, month, year)
);

CREATE INDEX IF NOT EXISTS idx_submissions_office_id
    ON submissions(office_id);

CREATE INDEX IF NOT EXISTS idx_submissions_status
    ON submissions(status);

COMMENT ON TABLE submissions IS 'التقارير الشهرية المُقدَّمة من المكاتب';
COMMENT ON COLUMN submissions.office_id IS 'مرجع للمكتب المُقدِّم';
COMMENT ON COLUMN submissions.submitter_name IS 'الاسم الثلاثي لمقدم التقرير';
COMMENT ON COLUMN submissions.submitter_phone IS 'رقم هاتف مقدم التقرير';
COMMENT ON COLUMN submissions.month IS 'الشهر المستهدف بالتقرير (1-12)';
COMMENT ON COLUMN submissions.year IS 'السنة المستهدفة بالتقرير';
COMMENT ON COLUMN submissions.has_plan IS 'هل يوجد خطة شهرية مكتوبة ومعتمدة';
COMMENT ON COLUMN submissions.plan_file_path IS 'مسار ملف الخطة الشهرية في Supabase Storage';
COMMENT ON COLUMN submissions.general_challenges IS 'التحديات والملاحظات الإدارية العامة';
COMMENT ON COLUMN submissions.additional_notes IS 'ملاحظات إضافية (اختياري)';
COMMENT ON COLUMN submissions.status IS 'حالة المعالجة: pending / processed / failed';


-- ─── 3. جدول المهام ────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tasks (
    id                      SERIAL PRIMARY KEY,
    submission_id           INTEGER NOT NULL
                            REFERENCES submissions(id) ON DELETE CASCADE,
    task_order              INTEGER NOT NULL,
    manager_name            TEXT NOT NULL,
    manager_phone           TEXT,
    task_name               TEXT NOT NULL,
    task_description        TEXT,
    task_type               TEXT
                            CHECK (task_type IN ('ضمن الخطة الشهرية', 'خارج الخطة الشهرية')),
    execution_mechanism     TEXT,
    task_status             TEXT
                            CHECK (task_status IN ('مكتملة', 'قيد التنفيذ', 'ملغاة')),
    issues                  TEXT,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tasks_submission_id
    ON tasks(submission_id);

COMMENT ON TABLE tasks IS 'المهام والمشاريع المرتبطة بكل تقرير شهري';
COMMENT ON COLUMN tasks.task_order IS 'ترتيب المهمة ضمن التقرير (1, 2, 3, ...)';
COMMENT ON COLUMN tasks.manager_name IS 'اسم المسؤول عن المهمة أو المشروع';
COMMENT ON COLUMN tasks.manager_phone IS 'رقم هاتف المسؤول';
COMMENT ON COLUMN tasks.task_name IS 'اسم المهمة أو المشروع';
COMMENT ON COLUMN tasks.task_description IS 'وصف قصير يوضح المهمة والهدف منها';
COMMENT ON COLUMN tasks.task_type IS 'نوع المهمة: ضمن الخطة الشهرية / خارج الخطة الشهرية';
COMMENT ON COLUMN tasks.execution_mechanism IS 'آلية التنفيذ — شرح الخطوات العملية';
COMMENT ON COLUMN tasks.task_status IS 'حالة المهمة: مكتملة / قيد التنفيذ / ملغاة';
COMMENT ON COLUMN tasks.issues IS 'المشاكل أو العقبات (إن وجدت)';


-- ─── 4. جدول الإجابات (EAV) — احتياطي مستقبلي فقط ────────────────────────
CREATE TABLE IF NOT EXISTS answers (
    id              SERIAL PRIMARY KEY,
    submission_id   INTEGER NOT NULL
                    REFERENCES submissions(id) ON DELETE CASCADE,
    question_key    TEXT NOT NULL,
    answer_value    TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_answers_submission_id
    ON answers(submission_id);

COMMENT ON TABLE answers IS 'جدول احتياطي (EAV) لأي أسئلة مستقبلية غير مخطط لها حالياً — فارغ بالوضع الراهن';


-- ─── Row Level Security (RLS) ──────────────────────────────────────────────
-- تفعيل RLS على الجداول مع سياسات السماح العام
-- (الفورم متاح للعامة بدون تسجيل دخول)

ALTER TABLE offices ENABLE ROW LEVEL SECURITY;
ALTER TABLE submissions ENABLE ROW LEVEL SECURITY;
ALTER TABLE tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE answers ENABLE ROW LEVEL SECURITY;

-- سياسة القراءة العامة للمكاتب (يحتاجها الفورم لعرض القائمة المنسدلة)
CREATE POLICY "offices_public_read" ON offices
    FOR SELECT
    USING (true);

-- سياسة الإدراج العام للتقارير (الفورم بدون auth)
CREATE POLICY "submissions_public_insert" ON submissions
    FOR INSERT
    WITH CHECK (true);

-- سياسة القراءة للتقارير (لاستخدام الباك اند فقط عبر service_role)
CREATE POLICY "submissions_service_read" ON submissions
    FOR SELECT
    USING (true);

-- سياسة الإدراج العام للمهام
CREATE POLICY "tasks_public_insert" ON tasks
    FOR INSERT
    WITH CHECK (true);

-- سياسة القراءة للمهام
CREATE POLICY "tasks_service_read" ON tasks
    FOR SELECT
    USING (true);

-- سياسة الإدراج العام للإجابات الاحتياطية
CREATE POLICY "answers_public_insert" ON answers
    FOR INSERT
    WITH CHECK (true);

-- سياسة القراءة للإجابات
CREATE POLICY "answers_service_read" ON answers
    FOR SELECT
    USING (true);
