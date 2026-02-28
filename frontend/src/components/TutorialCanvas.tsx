import { useState, useEffect } from "react";
import type { TutorialData } from "../api";

interface Props {
  tutorialData: TutorialData;
  onAskHelp: (stepIndex: number, question: string) => void;
}

export default function TutorialCanvas({ tutorialData, onAskHelp }: Props) {
  const [currentStep, setCurrentStep] = useState(0);

  const steps = tutorialData.steps || [];
  const s = steps[currentStep];

  // Force animation re-trigger when step changes
  useEffect(() => {
    const el = document.getElementById("step-content-anim");
    if (el) {
      el.style.animation = "none";
      void el.offsetHeight; // trigger reflow
      el.style.animation = "fadeSlide 0.4s cubic-bezier(0.4, 0, 0.2, 1) forwards";
    }
  }, [currentStep]);

  if (!steps.length) return null;

  const nextStep = () => {
    if (currentStep < steps.length - 1) {
      setCurrentStep(currentStep + 1);
    }
  };

  const prevStep = () => {
    if (currentStep > 0) {
      setCurrentStep(currentStep - 1);
    }
  };

  const goTo = (i: number) => {
    setCurrentStep(i);
  };

  return (
    <div className="max-w-[480px] mx-auto pb-6">
      <div className="bg-white rounded-[20px] p-6 shadow-[0_2px_20px_rgba(93,64,55,0.08)] mb-5">

        {/* Project Header */}
        <div className="font-caveat text-2xl text-[#3E2723] mb-1">
          {tutorialData.project_name}
        </div>
        <div className="flex gap-3 text-xs text-[#6D4C41] mb-4">
          <span className="flex items-center gap-1">
            <span className="w-[5px] h-[5px] rounded-full inline-block bg-[#6BAB73]"></span>{" "}
            {tutorialData.difficulty}
          </span>
          <span className="flex items-center gap-1">⏱ {tutorialData.time_estimate}</span>
        </div>

        {/* Step Navigation Dots */}
        <div className="flex items-center justify-center gap-1.5 mb-5">
          {steps.map((_, i) => (
            <div
              key={i}
              onClick={() => goTo(i)}
              className={`h-[10px] rounded-full transition-all duration-400 ease-[cubic-bezier(0.4,0,0.2,1)] cursor-pointer
                ${i === currentStep
                  ? "w-[32px] bg-[#F4845F] rounded-[5px]"
                  : i < currentStep
                    ? "w-[10px] bg-[#6BAB73]"
                    : "w-[10px] bg-[#FDDCB5]"
                }
              `}
            ></div>
          ))}
        </div>

        {/* SVG Frame */}
        <div className="bg-[#FFF9F0] rounded-2xl p-4 mb-4 flex items-center justify-center min-h-[300px] relative overflow-hidden border border-[#FDDCB5]/50 drop-shadow-[0_2px_8px_rgba(0,0,0,0.06)]">
          {s?.svg ? (
            <div
              className="w-full h-full [&>svg]:max-w-full [&>svg]:h-auto"
              dangerouslySetInnerHTML={{ __html: s.svg }}
            />
          ) : (
            <div className="text-gray-400 text-sm"></div>
          )}
        </div>

        {/* Step Content */}
        <div id="step-content-anim" className="opacity-0">
          <div className="text-[0.7rem] font-bold uppercase tracking-[2px] text-[#F4845F] mb-1.5">
            {tutorialData.ui?.step_label || "Step"} {currentStep + 1} {tutorialData.ui?.of_label || "of"} {steps.length}
          </div>
          <div className="font-caveat text-[1.35rem] text-[#3E2723] mb-2">
            {s.title}
          </div>
          <div className="text-[0.9rem] leading-[1.65] text-[#6D4C41] mb-4">
            {s.description}
          </div>

          {s.materials && s.materials.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mb-5">
              {s.materials.map((m, idx) => (
                <span
                  key={idx}
                  className="bg-[#FEF0E1] text-[#8D6E63] text-[0.75rem] font-semibold px-3 py-1.5 rounded-full"
                >
                  {m}
                </span>
              ))}
            </div>
          )}

          {s.tip && (
            <div className="bg-[#E8F5E9] rounded-xl p-3 px-4 flex gap-2.5 items-start mb-5">
              <span className="text-[1.1rem] mt-[1px]">💡</span>
              <span className="text-[0.82rem] text-[#6BAB73] leading-[1.5] font-medium">
                {s.tip}
              </span>
            </div>
          )}
        </div>

        {/* Buttons */}
        <div className="flex gap-2.5">
          <button
            onClick={prevStep}
            disabled={currentStep === 0}
            className="flex-1 p-[14px] rounded-[14px] border-none font-quicksand text-[0.95rem] font-bold cursor-pointer transition-all duration-250 bg-[#FEF0E1] text-[#8D6E63] hover:bg-[#FDDCB5] disabled:opacity-40 disabled:cursor-default"
          >
            ← {tutorialData.ui?.back_btn || "Back"}
          </button>
          <button
            onClick={nextStep}
            className="flex-1 p-[14px] rounded-[14px] border-none font-quicksand text-[0.95rem] font-bold cursor-pointer transition-all duration-250 bg-[#F4845F] text-white shadow-[0_4px_14px_rgba(244,132,95,0.35)] hover:bg-[#e5734f] hover:-translate-y-[1px] hover:shadow-[0_6px_20px_rgba(244,132,95,0.4)]"
          >
            {currentStep === steps.length - 1 ? `🎉 ${tutorialData.ui?.done_btn || "Done!"}` : `${tutorialData.ui?.next_btn || "Next"} →`}
          </button>
        </div>
      </div>

      {/* Quick Action Buttons per step */}
      <div className="flex gap-3 justify-center">
        <button
          onClick={() => onAskHelp(currentStep, `step_index:${currentStep}| Objasni mi ovaj korak`)}
          className="bg-white/60 hover:bg-white text-[#F4845F] text-xs font-semibold px-4 py-2 rounded-full shadow-sm hover:shadow-md transition-all border border-[#F4845F]/20"
        >
          🙋 Ask for Help
        </button>

      </div>
    </div>
  );
}
