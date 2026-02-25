import { useState } from "react";
import type { CraftData } from "../api";

interface Props {
  data: CraftData;
}

export default function CraftingWidget({ data }: Props) {
  const [currentStep, setCurrentStep] = useState(0);
  const step = data.steps[currentStep];
  const total = data.steps.length;

  return (
    <div className="bg-white border border-gray-200 rounded-2xl overflow-hidden shadow-sm mt-3">
      {/* Header */}
      <div className="bg-gray-50 px-4 py-3 border-b border-gray-200 flex justify-between items-center">
        <div>
          <h4 className="font-bold text-gray-800 text-sm">{data.projectName}</h4>
          <p className="text-xs text-gray-500">
            {data.difficulty} &bull; {data.estimatedTime}
          </p>
        </div>
        <div className="bg-emerald-100 text-emerald-700 px-2 py-1 rounded text-xs font-bold">
          {currentStep + 1}/{total}
        </div>
      </div>

      {/* SVG Display */}
      <div className="p-4 flex justify-center bg-gray-50">
        <div className="w-48 h-48 bg-white rounded-xl shadow-inner border border-gray-100 p-2">
          <div
            className="w-full h-full"
            dangerouslySetInnerHTML={{ __html: step.svgCode }}
          />
        </div>
      </div>

      {/* Step Description */}
      <div className="px-4 py-3">
        <h5 className="font-bold text-gray-800 text-sm mb-1">{step.title}</h5>
        <p className="text-gray-600 text-xs leading-relaxed">{step.description}</p>
      </div>

      {/* Materials (show only on first step) */}
      {currentStep === 0 && data.materials && data.materials.length > 0 && (
        <div className="px-4 pb-3">
          <p className="text-xs text-gray-500 font-semibold mb-1">Materials:</p>
          <div className="flex flex-wrap gap-1">
            {data.materials.map((m, i) => (
              <span key={i} className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded">
                {m}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Navigation */}
      <div className="px-4 py-3 bg-gray-50 border-t border-gray-200 flex gap-2">
        <button
          onClick={() => setCurrentStep((c) => Math.max(0, c - 1))}
          disabled={currentStep === 0}
          className="flex-1 py-2 px-3 rounded-lg text-xs font-medium disabled:opacity-40 border border-gray-200 bg-white text-gray-600 hover:bg-gray-100"
        >
          &larr; Back
        </button>
        <button
          onClick={() => setCurrentStep((c) => Math.min(total - 1, c + 1))}
          disabled={currentStep === total - 1}
          className="flex-1 py-2 px-3 rounded-lg text-xs font-medium bg-emerald-600 text-white hover:bg-emerald-700 disabled:opacity-40"
        >
          Next &rarr;
        </button>
      </div>
    </div>
  );
}
