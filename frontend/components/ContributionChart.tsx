"use client";

import type { Contributor } from "@/lib/api";

/** Diverging horizontal bar chart of the strongest feature contributions. */
export default function ContributionChart({
  contributions,
}: {
  contributions: Contributor[];
}) {
  const positives = contributions.filter((c) => c.shap_value > 0).slice(0, 3);
  const negatives = contributions
    .filter((c) => c.shap_value < 0)
    .slice(-3); // sorted most-positive first, so negatives sit at the end
  const bars = [...positives, ...negatives];
  if (bars.length === 0) return null;

  const maxAbs = Math.max(...bars.map((c) => Math.abs(c.shap_value)), 1);

  return (
    <div className="space-y-2.5">
      {bars.map((c) => {
        const width = (Math.abs(c.shap_value) / maxAbs) * 50;
        const positive = c.shap_value > 0;
        return (
          <div key={c.feature} className="flex items-center gap-3">
            <div className="w-44 shrink-0 truncate text-right text-xs font-medium text-slate-600 sm:w-56">
              {c.feature}
              <span className="block text-[10px] font-normal text-slate-400">
                {c.value}
              </span>
            </div>
            <div className="relative h-5 flex-1">
              <span className="absolute inset-y-0 left-1/2 w-px bg-slate-300" />
              {positive ? (
                <span
                  className="absolute bottom-0.5 left-1/2 top-0.5 rounded-r-md bg-emerald-600"
                  style={{ width: `${width}%` }}
                />
              ) : (
                <span
                  className="absolute bottom-0.5 right-1/2 top-0.5 rounded-l-md bg-red-600"
                  style={{ width: `${width}%` }}
                />
              )}
            </div>
            <div
              className={`w-14 shrink-0 text-right text-xs font-semibold ${
                positive ? "text-emerald-700" : "text-red-700"
              }`}
            >
              {c.shap_value > 0 ? "+" : ""}
              {c.shap_value.toFixed(1)}
            </div>
          </div>
        );
      })}
      <p className="pt-1 text-center text-[11px] text-slate-500">
        How strongly each feature moved the model&apos;s score for this applicant
        (points) — green raised the score, red lowered it.
      </p>
    </div>
  );
}
