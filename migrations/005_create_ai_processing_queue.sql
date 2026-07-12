-- ============================================================================
-- GUSS — Migration 005: Create AI Processing Queue
-- ============================================================================
-- جدول طابور معالجة الذكاء الاصطناعي لمعالجة التقارير بشكل غير متزامن
-- يُنفَّذ في Supabase SQL Editor يدوياً بعد مراجعة وموافقة الفريق الهندسي
-- ============================================================================

-- ─── 1. جدول الطابور ────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ai_processing_queue (
    id              INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    submission_id   INTEGER NOT NULL
                    REFERENCES submissions(id),
    status          TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'processing', 'done', 'failed')),
    attempts        INTEGER NOT NULL DEFAULT 0,
    error_message   TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    processed_at    TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_queue_status
    ON ai_processing_queue(status, created_at);

COMMENT ON TABLE ai_processing_queue IS 'طابور معالجة الذكاء الاصطناعي — يُدار حصراً بواسطة الباك اند عبر service_role';
COMMENT ON COLUMN ai_processing_queue.submission_id IS 'مرجع للتقرير المُراد معالجته';
COMMENT ON COLUMN ai_processing_queue.status IS 'حالة المعالجة: pending / processing / done / failed';
COMMENT ON COLUMN ai_processing_queue.attempts IS 'عدد محاولات المعالجة (الحد الأقصى محدد في settings.yaml)';
COMMENT ON COLUMN ai_processing_queue.error_message IS 'رسالة الخطأ عند الفشل (آخر محاولة فاشلة)';
COMMENT ON COLUMN ai_processing_queue.created_at IS 'وقت إضافة السجل للطابور';
COMMENT ON COLUMN ai_processing_queue.processed_at IS 'وقت اكتمال المعالجة (done أو failed النهائي)';


-- ─── 2. Row Level Security (RLS) ────────────────────────────────────────────
-- هذا الجدول مخصص حصراً للباك اند — لا يجب أن يصل إليه أي مستخدم عام.
--
-- ملاحظة تصميمية:
--   في Supabase، يتجاوز دور service_role سياسات RLS تلقائياً (BYPASSRLS).
--   لذا الهدف الأساسي من تفعيل RLS هنا هو:
--   (أ) منع أي وصول عبر anon key أو authenticated users بالكامل
--   (ب) توثيق قصد التصميم صراحةً — هذا الجدول ليس جدولاً عاماً
--
-- لا توجد سياسة SELECT/INSERT/UPDATE/DELETE مفتوحة للعموم هنا.
-- الباك اند يستخدم SUPABASE_SERVICE_ROLE_KEY الذي يتجاوز RLS دائماً.
-- ────────────────────────────────────────────────────────────────────────────

ALTER TABLE ai_processing_queue ENABLE ROW LEVEL SECURITY;

-- ─── منع أي وصول عبر anon أو authenticated ──────────────────────────────────
-- لا يوجد USING (true) هنا عن قصد — كل الوصول محجوب افتراضياً بمجرد تفعيل RLS.
-- الباك اند يعمل عبر service_role الذي يتجاوز RLS تلقائياً في Supabase.

-- سياسة صريحة للقراءة — service_role فقط (للتوثيق الكامل)
CREATE POLICY "queue_service_select" ON ai_processing_queue
    FOR SELECT
    USING (auth.role() = 'service_role');

-- سياسة صريحة للإدراج — service_role فقط
CREATE POLICY "queue_service_insert" ON ai_processing_queue
    FOR INSERT
    WITH CHECK (auth.role() = 'service_role');

-- سياسة صريحة للتحديث — service_role فقط (تحديث status, attempts, error_message)
CREATE POLICY "queue_service_update" ON ai_processing_queue
    FOR UPDATE
    USING (auth.role() = 'service_role');

-- سياسة صريحة للحذف — service_role فقط (للتنظيف الدوري إن لزم)
CREATE POLICY "queue_service_delete" ON ai_processing_queue
    FOR DELETE
    USING (auth.role() = 'service_role');
