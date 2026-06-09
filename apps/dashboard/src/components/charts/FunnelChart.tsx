"use client";

interface FunnelStep {
  label: string;
  value: number;
  rate?: string;
}

interface Props {
  steps: FunnelStep[];
}

export default function FunnelChart({ steps }: Props) {
  const max = Math.max(...steps.map((s) => s.value), 1);

  return (
    <div className="flex flex-col gap-2">
      {steps.map((step, i) => (
        <div key={i} className="flex items-center gap-3">
          <span className="w-40 text-right text-xs text-gray-500 shrink-0">{step.label}</span>
          <div className="flex-1 bg-gray-100 rounded-full h-6 overflow-hidden">
            <div
              className="h-6 rounded-full bg-indigo-500 flex items-center justify-end pr-3 transition-all"
              style={{ width: `${(step.value / max) * 100}%` }}
            >
              <span className="text-xs text-white font-medium">
                {step.value.toLocaleString("pt-BR")}
              </span>
            </div>
          </div>
          {step.rate && (
            <span className="text-xs text-gray-400 w-16 shrink-0">{step.rate}</span>
          )}
        </div>
      ))}
    </div>
  );
}
