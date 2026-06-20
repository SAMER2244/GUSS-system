-- ============================================================================
-- GUSS — Migration 003: Supabase Storage Bucket
-- ============================================================================
-- إنشاء bucket خاص لرفع ملفات الخطط الشهرية (PDF)
-- يُنفَّذ في Supabase SQL Editor
-- ============================================================================

-- إنشاء bucket خاص (غير عام — يتطلب signed URLs للوصول)
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES (
    'monthly-plans',
    'monthly-plans',
    FALSE,                              -- private bucket
    10485760,                           -- 10 MB max file size
    ARRAY['application/pdf']::text[]    -- PDF files only
)
ON CONFLICT (id) DO NOTHING;

-- ─── Storage Policies ──────────────────────────────────────────────────────

-- سياسة الرفع العام (الفورم بدون auth — يرفع أي مستخدم)
CREATE POLICY "monthly_plans_public_upload"
    ON storage.objects
    FOR INSERT
    WITH CHECK (
        bucket_id = 'monthly-plans'
    );

-- سياسة القراءة عبر service_role فقط (للباك اند)
CREATE POLICY "monthly_plans_service_read"
    ON storage.objects
    FOR SELECT
    USING (
        bucket_id = 'monthly-plans'
    );
