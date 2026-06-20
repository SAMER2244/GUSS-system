import React from 'react';

export default function ProgressIndicator({ currentStep, totalSteps = 4, onStepClick }) {
  const stepLabels = [
    'الترحيب',
    'البيانات الأساسية',
    'بيانات المهام',
    'البيانات الختامية'
  ];

  // Calculate width percentage for the connecting line
  // Step 1: 0%, Step 2: 33.3%, Step 3: 66.6%, Step 4: 100%
  const fillWidth = `${((currentStep - 1) / (totalSteps - 1)) * 100}%`;

  return (
    <div className="progress-container">
      <div className="progress-line">
        <div className="progress-line-fill" style={{ width: fillWidth, right: 0 }} />
      </div>
      
      {Array.from({ length: totalSteps }, (_, i) => {
        const stepNum = i + 1;
        const isActive = stepNum === currentStep;
        const isCompleted = stepNum < currentStep;
        
        let stepClass = 'progress-step';
        if (isActive) stepClass += ' active';
        if (isCompleted) stepClass += ' completed';

        return (
          <button
            key={stepNum}
            type="button"
            className={stepClass}
            onClick={() => onStepClick && onStepClick(stepNum)}
            disabled={!isCompleted && stepNum > currentStep} // Only allow clicking past completed steps or current step
            title={stepLabels[i]}
          >
            {isCompleted ? <i className="fa-solid fa-check"></i> : stepNum}
            <span className="progress-step-label">{stepLabels[i]}</span>
          </button>
        );
      })}
    </div>
  );
}
