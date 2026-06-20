import React from 'react';

export default function WelcomeStep({ onNext }) {
  return (
    <div className="welcome-desc-card animate-slide-up">
      <div className="welcome-info-box">
        <p style={{ fontSize: '1.1rem', fontWeight: 'bold', marginBottom: '1rem' }}>
          يهدف هذا النموذج إلى بناء أرشيف رقمي متكامل ومؤسساتي لأعمال الاتحاد لضمان توثيق جهود المكاتب وحفظ إنجازاتها وفق أعلى المعايير المهنية والتقنية.
        </p>
        <p style={{ marginBottom: '1rem' }}>
          يرجى التقيّد بالتعليمات التالية لضمان دقة التقارير:
        </p>
        <p style={{ marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <i className="fa-solid fa-circle-info" style={{ color: 'var(--color-gold)' }}></i>
          يرجى قراءة الدليل الإرشادي المرفق بشكل تفصيلي لضمان دقة التقارير المرفقة:
        </p>
        
        <div style={{ textAlign: 'center', margin: '2rem 0' }}>
          <a 
            href="https://drive.google.com/drive/u/2/folders/1SqJq68IhOp7dG7stvBQvG3UlrG8PK5y9" 
            target="_blank" 
            rel="noopener noreferrer" 
            className="guide-link"
            style={{ fontSize: '1.25rem', padding: '0.75rem 1.5rem', background: 'var(--color-gold-light)', borderRadius: '8px', border: '1px solid var(--color-gold)', display: 'inline-block' }}
          >
            <i className="fa-solid fa-book-open" style={{ marginLeft: '0.5rem' }}></i>
            الدليل الإرشادي لمنظومة المتابعة الدورية
          </a>
        </div>

        <p style={{ textAlign: 'center', fontWeight: 'bold', marginTop: '1.5rem', color: 'var(--text-secondary)' }}>
          أعانكم الله.
        </p>
      </div>

      <div className="btn-group" style={{ justifyContent: 'center' }}>
        <button 
          type="button" 
          onClick={onNext} 
          className="btn btn-primary"
          style={{ padding: '0.9rem 3rem', fontSize: '1.1rem' }}
        >
          البدء بتعبئة التقرير
          <i className="fa-solid fa-arrow-left btn-icon"></i>
        </button>
      </div>
    </div>
  );
}
