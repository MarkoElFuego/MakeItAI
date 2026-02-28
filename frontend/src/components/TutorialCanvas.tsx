import { useState, useEffect } from "react";
import type { TutorialData } from "../api";

interface Props {
  tutorialData: TutorialData;
  onAskHelp: (stepIndex: number, question: string) => void;
  onComplete?: () => void;
}

export default function TutorialCanvas({ tutorialData, onAskHelp, onComplete }: Props) {
  const [currentStep, setCurrentStep] = useState(0);
  const [completed, setCompleted] = useState<Set<number>>(new Set());

  const steps = tutorialData.steps || [];
  const s = steps[currentStep];
  const progress = Math.round((completed.size / steps.length) * 100);

  useEffect(() => {
    const el = document.getElementById("step-content-anim");
    if (el) {
      el.style.animation = "none";
      void el.offsetHeight;
      el.style.animation = "fadeSlide 0.4s cubic-bezier(0.4, 0, 0.2, 1) forwards";
    }
  }, [currentStep]);

  if (!steps.length) return null;

  const toggleComplete = (idx: number) => {
    setCompleted((prev) => {
      const next = new Set(prev);
      if (next.has(idx)) {
        next.delete(idx);
      } else {
        next.add(idx);
      }
      // Check if all complete
      if (next.size === steps.length && onComplete) {
        setTimeout(() => onComplete(), 500);
      }
      return next;
    });
  };

  const nextStep = () => {
    if (currentStep < steps.length - 1) setCurrentStep(currentStep + 1);
  };

  const prevStep = () => {
    if (currentStep > 0) setCurrentStep(currentStep - 1);
  };

  const youtubeUrl = (query: string) =>
    `https://www.youtube.com/results?search_query=${encodeURIComponent(query)}`;

  return (
    <div className="tutorial-canvas">
      <div className="tutorial-card">

        {/* Project Header */}
        <div className="tutorial-header">
          <h2 className="tutorial-title">{tutorialData.project_name}</h2>
          <div className="tutorial-meta">
            <span className="meta-badge difficulty">{tutorialData.difficulty}</span>
            <span className="meta-badge time">⏱ {tutorialData.time_estimate}</span>
          </div>
        </div>

        {/* Progress Bar */}
        <div className="progress-container">
          <div className="progress-bar">
            <div className="progress-fill" style={{ width: `${progress}%` }} />
          </div>
          <span className="progress-text">{completed.size}/{steps.length} complete</span>
        </div>

        {/* Step Navigation Dots */}
        <div className="step-dots">
          {steps.map((_, i) => (
            <div
              key={i}
              onClick={() => setCurrentStep(i)}
              className={`step-dot ${i === currentStep ? "active" :
                  completed.has(i) ? "done" : "pending"
                }`}
            />
          ))}
        </div>

        {/* Step Card (No SVG!) */}
        <div id="step-content-anim" className="step-card-anim">

          {/* Step Number */}
          <div className="step-number">
            {tutorialData.ui?.step_label || "Step"} {currentStep + 1} {tutorialData.ui?.of_label || "of"} {steps.length}
          </div>

          {/* Title + Checkbox */}
          <div className="step-title-row">
            <button
              className={`step-checkbox ${completed.has(currentStep) ? "checked" : ""}`}
              onClick={() => toggleComplete(currentStep)}
            >
              {completed.has(currentStep) ? "✓" : ""}
            </button>
            <h3 className={`step-title ${completed.has(currentStep) ? "completed" : ""}`}>
              {s.title}
            </h3>
          </div>

          {/* Description */}
          <div className="step-description">
            {s.description}
          </div>

          {/* Materials */}
          {s.materials && s.materials.length > 0 && (
            <div className="step-materials">
              {s.materials.map((m, idx) => (
                <span key={idx} className="material-tag">📦 {m}</span>
              ))}
            </div>
          )}

          {/* Tip */}
          {s.tip && (
            <div className="step-tip">
              <span className="tip-icon">💡</span>
              <span className="tip-text">{s.tip}</span>
            </div>
          )}

          {/* YouTube Link */}
          {s.youtube_query && (
            <a
              href={youtubeUrl(s.youtube_query)}
              target="_blank"
              rel="noopener noreferrer"
              className="youtube-link"
            >
              ▶️ Watch video tutorial for this step
            </a>
          )}
        </div>

        {/* Navigation Buttons */}
        <div className="step-buttons">
          <button
            onClick={prevStep}
            disabled={currentStep === 0}
            className="btn-prev"
          >
            ← {tutorialData.ui?.back_btn || "Back"}
          </button>
          <button
            onClick={() => {
              toggleComplete(currentStep);
              if (currentStep < steps.length - 1) nextStep();
            }}
            className="btn-next"
          >
            {currentStep === steps.length - 1
              ? `🎉 ${tutorialData.ui?.done_btn || "Done!"}`
              : `${tutorialData.ui?.next_btn || "Next"} →`}
          </button>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="step-actions">
        <button
          onClick={() =>
            onAskHelp(currentStep, `step_index:${currentStep}| Objasni mi ovaj korak`)
          }
          className="btn-help"
        >
          🙋 Ask for Help
        </button>
      </div>
    </div>
  );
}
