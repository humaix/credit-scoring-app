"use client";

import { CATEGORY_COLORS } from "@/lib/api";

/** Semicircular score gauge coloured by assessment category. */
export default function ScoreGauge({
  score,
  category,
}: {
  score: number;
  category: string;
}) {
  const color = CATEGORY_COLORS[category] ?? "#334155";
  const clamped = Math.min(Math.max(score, 0), 100);
  const arcLength = Math.PI * 80; // semicircle radius 80
  const dash = (clamped / 100) * arcLength;

  return (
    <div className="flex flex-col items-center">
      <svg viewBox="0 0 200 108" className="w-64" role="img" aria-label={`Score ${score} of 100`}>
        <path
          d="M 20 92 A 80 80 0 0 1 180 92"
          fill="none"
          stroke="#e2e8f0"
          strokeWidth="14"
          strokeLinecap="round"
        />
        <path
          d="M 20 92 A 80 80 0 0 1 180 92"
          fill="none"
          stroke={color}
          strokeWidth="14"
          strokeLinecap="round"
          strokeDasharray={`${dash} ${arcLength}`}
        />
        <text
          x="100"
          y="72"
          textAnchor="middle"
          className="fill-slate-900"
          style={{ fontSize: "30px", fontWeight: 700 }}
        >
          {score.toFixed(1)}
        </text>
        <text
          x="100"
          y="90"
          textAnchor="middle"
          style={{ fontSize: "11px", fill: "#64748b" }}
        >
          out of 100
        </text>
        <text x="20" y="106" style={{ fontSize: "10px", fill: "#94a3b8" }}>
          0
        </text>
        <text x="170" y="106" style={{ fontSize: "10px", fill: "#94a3b8" }}>
          100
        </text>
      </svg>
      <span
        className="-mt-1 rounded-full px-3.5 py-1.5 text-sm font-bold text-white"
        style={{ backgroundColor: color }}
      >
        {category}
      </span>
    </div>
  );
}
