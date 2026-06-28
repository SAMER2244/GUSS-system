import React, { useState, useEffect } from 'react';
import WelcomeStep from './components/WelcomeStep';
import BasicInfoStep from './components/BasicInfoStep';
import TasksStep from './components/TasksStep';
import ClosingStep from './components/ClosingStep';
import SuccessScreen from './components/SuccessScreen';
import ProgressIndicator from './components/ProgressIndicator';
import ThemeToggle from './components/ThemeToggle';

const INITIAL_FORM_STATE = {
  // Page 2: Basic Info
  office_name: '',
  custom_office_name: '',
  submitter_name: '',
  submitter_phone: '',
  month: new Date().getMonth() + 1, // current month (1-12)
  year: 2026,
  has_plan: true,
  plan_file: null,

  // Page 3: Tasks
  tasks: [
    {
      manager_name: '',
      manager_phone: '',
      task_name: '',
      task_description: '',
      task_type: 'ضمن الخطة الشهرية',
      execution_mechanism: '',
      task_status: 'مكتملة',
      issues: ''
    }
  ],

  // Page 4: Closing Info
  general_challenges: '',
  additional_notes: ''
};

export default function App() {
  const [step, setStep] = useState(1);
  const [formData, setFormData] = useState(INITIAL_FORM_STATE);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitStage, setSubmitStage] = useState(''); // 'uploading' | 'submitting' | ''
  const [submitError, setSubmitError] = useState('');
  const [submissionId, setSubmissionId] = useState(null);

  // Auto-Save States
  const [showRestoreModal, setShowRestoreModal] = useState(false);
  const [restoredDraft, setRestoredDraft] = useState(null);
  const [isRestoredPlan, setIsRestoredPlan] = useState(false);

  // 1. Check for saved draft on initial load
  useEffect(() => {
    try {
      const saved = localStorage.getItem('guss_form_draft');
      if (saved) {
        const parsed = JSON.parse(saved);
        if (parsed && parsed.formData) {
          setRestoredDraft(parsed);
          setShowRestoreModal(true);
        }
      }
    } catch (err) {
      console.warn('Failed to read draft from localStorage:', err);
    }
  }, []);

  // 2. Auto-Save debounced effect
  useEffect(() => {
    if (step === 5) return; // Do not auto-save on successful submission screen

    const isInitial = step === 1 && 
                      formData.office_name === '' && 
                      formData.submitter_name === '' && 
                      formData.submitter_phone === '';

    const timer = setTimeout(() => {
      try {
        if (isInitial) {
          localStorage.removeItem('guss_form_draft');
        } else {
          const { plan_file, ...serializableData } = formData;
          const draft = {
            step,
            formData: serializableData
          };
          localStorage.setItem('guss_form_draft', JSON.stringify(draft));
        }
      } catch (err) {
        console.warn('Failed to update draft in localStorage:', err);
      }
    }, 500);

    return () => clearTimeout(timer);
  }, [formData, step]);

  const handleRestore = () => {
    if (restoredDraft) {
      setFormData(prev => ({
        ...prev,
        ...restoredDraft.formData,
        plan_file: null // Files cannot be serialised, user must re-select
      }));
      setStep(restoredDraft.step || 1);
      if (restoredDraft.formData.has_plan) {
        setIsRestoredPlan(true);
      }
    }
    setShowRestoreModal(false);
    setRestoredDraft(null);
  };

  const handleDiscardRestore = () => {
    try {
      localStorage.removeItem('guss_form_draft');
    } catch (err) {
      console.warn('Failed to delete draft from localStorage:', err);
    }
    setShowRestoreModal(false);
    setRestoredDraft(null);
  };

  const updateFormData = (newData) => {
    setFormData(prev => ({
      ...prev,
      ...newData
    }));
    // If user changes/removes the plan file, clear the restored warning
    if ('plan_file' in newData) {
      setIsRestoredPlan(false);
    }
  };

  const handleNext = () => {
    setStep(prev => Math.min(prev + 1, 4));
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const handlePrev = () => {
    setStep(prev => Math.max(prev - 1, 1));
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const handleStepClick = (targetStep) => {
    // Only allow clicking to step if it is less than current step
    if (targetStep < step) {
      setStep(targetStep);
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }
  };

  const handleReset = () => {
    setFormData(INITIAL_FORM_STATE);
    setSubmissionId(null);
    setSubmitError('');
    setStep(1);
    setIsRestoredPlan(false);
    try {
      localStorage.removeItem('guss_form_draft');
    } catch (err) {
      console.warn('Failed to remove draft on reset:', err);
    }
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const handleSubmit = async () => {
    setIsSubmitting(true);
    setSubmitError('');
    
    const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || '';
    let planFilePath = null;

    // ─── a. Upload monthly plan PDF if has_plan is true ───
    if (formData.has_plan && formData.plan_file) {
      setSubmitStage('uploading');
      try {
        const filePayload = new FormData();
        filePayload.append('file', formData.plan_file);

        const uploadRes = await fetch(`${apiBaseUrl}/api/upload-plan`, {
          method: 'POST',
          body: filePayload
        });

        const uploadData = await uploadRes.json();
        
        if (!uploadRes.ok) {
          throw new Error(uploadData.detail || 'فشل رفع ملف الخطة الشهرية إلى السحابة.');
        }

        planFilePath = uploadData.file_path;
      } catch (err) {
        console.error('File upload error:', err);
        setSubmitError(err.message || 'حدث خطأ أثناء رفع ملف PDF. يرجى التحقق من حجم الملف والاتصال بالشبكة.');
        setIsSubmitting(false);
        setSubmitStage('');
        return;
      }
    }

    // ─── b. Submit the final report ───
    setSubmitStage('submitting');
    try {
      const officeName = formData.office_name === 'غير ذلك' 
        ? formData.custom_office_name 
        : formData.office_name;

      const reportPayload = {
        office_name: officeName,
        submitter_name: formData.submitter_name,
        submitter_phone: formData.submitter_phone,
        month: parseInt(formData.month),
        year: parseInt(formData.year),
        has_plan: formData.has_plan,
        plan_file_path: planFilePath,
        tasks: formData.tasks.map(t => ({
          manager_name: t.manager_name,
          manager_phone: t.manager_phone,
          task_name: t.task_name,
          task_description: t.task_description || null,
          task_type: t.task_type,
          execution_mechanism: t.execution_mechanism,
          task_status: t.task_status,
          issues: t.issues || null
        })),
        general_challenges: formData.general_challenges,
        additional_notes: formData.additional_notes || null
      };

      const submitRes = await fetch(`${apiBaseUrl}/api/submit-report`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(reportPayload)
      });

      const submitData = await submitRes.json();

      if (!submitRes.ok) {
        if (submitRes.status === 409) {
          throw new Error(`يوجد تقرير مسجل مسبقاً لمكتب "${officeName}" عن شهر ${formData.month}/${formData.year}. لا يمكن تقديم تقرير مكرر لنفس الفترة.`);
        }
        if (submitRes.status === 404) {
          throw new Error(`المكتب "${officeName}" غير مسجل في المنظومة. يرجى اختيار مكتب من القائمة.`);
        }
        throw new Error(submitData.detail || 'فشل إرسال التقرير النهائي لقاعدة البيانات.');
      }

      // Success
      setSubmissionId(submitData.submission_id);
      setStep(5); // Go to success screen
      
      try {
        localStorage.removeItem('guss_form_draft');
      } catch (err) {
        console.warn('Failed to remove draft on success:', err);
      }

    } catch (err) {
      console.error('Report submission error:', err);
      setSubmitError(err.message || 'حدث خطأ غير متوقع أثناء حفظ التقرير في قاعدة البيانات.');
    } finally {
      setIsSubmitting(false);
      setSubmitStage('');
    }
  };

  return (
    <div className="app-container">
      {/* Header Banner */}
      <header className="form-header">
        {/* Theme Toggle Button placed elegantly inside header */}
        <ThemeToggle />

        <img src="/assets/office_bg.jpeg" alt="الاتحاد العام لطلبة سوريا" className="banner-img" />
        <div className="header-overlay"></div>
        <div className="header-content">
          <div className="title-container">
            <h1>منظومة المتابعة الدورية</h1>
            <p>الاتحاد العام لطلبة سوريا - مكتب المتابعة و التقييم</p>
          </div>
        </div>
      </header>

      {/* Progress Indicator (only if not on success screen) */}
      {step <= 4 && (
        <ProgressIndicator currentStep={step} onStepClick={handleStepClick} />
      )}

      {/* Form Card container */}
      <main className="form-card">
        {/* Render submission errors if any */}
        {submitError && (
          <div className="alert alert-danger">
            <i className="fa-solid fa-circle-exclamation alert-icon"></i>
            <div>
              <strong>فشل الإرسال:</strong> {submitError}
            </div>
          </div>
        )}

        {/* Step Routing */}
        {step === 1 && (
          <WelcomeStep onNext={handleNext} />
        )}
        
        {step === 2 && (
          <BasicInfoStep 
            formData={formData} 
            updateFormData={updateFormData} 
            onNext={handleNext} 
            onPrev={handlePrev} 
            isRestoredPlan={isRestoredPlan}
          />
        )}

        {step === 3 && (
          <TasksStep 
            formData={formData} 
            updateFormData={updateFormData} 
            onNext={handleNext} 
            onPrev={handlePrev} 
          />
        )}

        {step === 4 && (
          <ClosingStep 
            formData={formData} 
            updateFormData={updateFormData} 
            onSubmit={handleSubmit} 
            onPrev={handlePrev} 
            isSubmitting={isSubmitting}
          />
        )}

        {step === 5 && (
          <SuccessScreen 
            submissionId={submissionId} 
            formData={formData} 
            onReset={handleReset} 
          />
        )}
      </main>

      {/* Submit Spinner Overlay */}
      {isSubmitting && (
        <div className="submit-overlay">
          <div className="submit-spinner-card">
            <div className="spinner"></div>
            {submitStage === 'uploading' ? (
              <>
                <h3>جاري رفع ملف الخطة...</h3>
                <p>يرجى الانتظار، يتم حالياً رفع ملف PDF الخاص بخطة المكتب إلى التخزين السحابي الآمن لـ Supabase.</p>
              </>
            ) : (
              <>
                <h3>جاري إرسال التقرير...</h3>
                <p>يرجى الانتظار، يتم حالياً ربط خطة المكتب بالمهام المرفقة وحفظ التقرير بالكامل في قاعدة البيانات.</p>
              </>
            )}
          </div>
        </div>
      )}

      {/* Restore Draft Modal Overlay */}
      {showRestoreModal && (
        <div className="submit-overlay">
          <div className="submit-spinner-card" style={{ maxWidth: '440px' }}>
            <i className="fa-solid fa-file-invoice" style={{ fontSize: '3rem', color: 'var(--color-gold)' }}></i>
            <h3 style={{ fontSize: '1.2rem', marginTop: '0.5rem' }}>تقرير غير مكتمل</h3>
            <p style={{ fontSize: '0.95rem', lineHeight: '1.6', margin: '0.5rem 0 1rem', color: 'var(--text-secondary)' }}>
              وجدنا تقريراً غير مكتمل من محاولة سابقة. هل تريد الاستمرار من حيث توقفت، أم البدء من جديد؟
            </p>
            <div style={{ display: 'flex', gap: '1rem', width: '100%' }}>
              <button 
                type="button" 
                onClick={handleRestore} 
                className="btn btn-primary" 
                style={{ flex: 1, padding: '0.75rem 1rem' }}
              >
                استمرار
              </button>
              <button 
                type="button" 
                onClick={handleDiscardRestore} 
                className="btn btn-secondary" 
                style={{ flex: 1, padding: '0.75rem 1rem' }}
              >
                بدء جديد
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Footer */}
      <footer className="form-footer">
        <div className="footer-content">
          <p className="footer-text">
            جميع الحقوق محفوظة © 2026 - <a href="https://guss.sy" target="_blank" rel="noopener noreferrer" className="footer-link">الاتحاد العام لطلبة سوريا</a> - مكتب المتابعة و التقييم
          </p>
        </div>
      </footer>
    </div>
  );
}
