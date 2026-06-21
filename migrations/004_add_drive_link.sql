-- ============================================================================
-- GUSS — Migration 004: Add drive_report_link to submissions
-- ============================================================================
-- يضيف عمود لحفظ رابط التقرير النهائي على Google Drive
-- بعد اكتمال المعالجة بالـ background pipeline.
-- يُنفَّذ في Supabase SQL Editor
-- ============================================================================

ALTER TABLE submissions ADD COLUMN IF NOT EXISTS drive_report_link TEXT;

COMMENT ON COLUMN submissions.drive_report_link IS 'رابط ملف التقرير النهائي على Google Drive (يُملأ تلقائياً بعد اكتمال المعالجة)';
