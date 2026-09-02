"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import { api } from "@/lib/api";
import {
  Alert, Card, ErrorBox, PageSpinner, PrimaryButton, Stepper,
  useCurrentApplication,
} from "@/components/ui";

const STAGES = [
  {
    title: "Assembling your features",
    text: "Your declared profile, the questionnaire score and the consented provider summaries are combined into the model's ten features.",
  },
  {
    title: "Estimating the repayment score",
    text: "The trained XGBoost model produces a 0–100 repayment assessment. The model is never modified.",
  },
  {
    title: "Explaining the score",
    text: "SHAP analysis works out exactly how much each feature raised or lowered the estimate, then the wording layer turns those contributions into plain English.",
  },
  {
    title: "Preparing your PDF report",
    text: "Everything — score, factors, explanation and disclaimer — is rendered into a downloadable report.",
  },
];

export default function ProcessingPage() {
  const router = useRouter();
  const { app, loading, error } = useCurrentApplication("assessed");

  const [running, setRunning] = useState(false);
  const [runError, setRunError] = useState<unknown>(null);

  if (loading) return <PageSpinner />;
  if (error) {
    return (
      <div className="mx-auto max-w-md">
        <ErrorBox error={error} />
      </div>
    );
  }
  if (!app) return null;

  async function runAssessment() {
    setRunning(true);
    setRunError(null);
    try {
      await api.post("/api/scoring/predict", { application_id: app!.id });
      router.push("/results");
    } catch (err) {
      setRunError(err);
      setRunning(false);
    }
  }

  return (
    <div className="mx-auto max-w-xl">
      <Stepper current={4} />
      <Card>
        <h1 className="text-xl font-bold tracking-tight text-slate-900">
          Ready to run your assessment
        </h1>
        <p className="mt-1 text-sm text-slate-600">
          Everything is in place. Here&apos;s what happens when you press the
          button — nothing is hidden.
        </p>

        <ol className="mt-6 space-y-3">
          {STAGES.map((stage, index) => (
            <li
              key={stage.title}
              className="rise-in flex gap-3 rounded-xl border border-slate-200 bg-white p-4"
              style={{ animationDelay: `${index * 0.12}s` }}
            >
              <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-[#0c2f48] text-xs font-bold text-white">
                {index + 1}
              </span>
              <div>
                <p className="text-sm font-semibold text-slate-900">
                  {stage.title}
                </p>
                <p className="mt-0.5 text-xs leading-relaxed text-slate-600">
                  {stage.text}
                </p>
              </div>
            </li>
          ))}
        </ol>

        <div className="mt-5">
          <Alert tone="info">
            Telecom and wallet summaries are simulated for this prototype (no
            real provider is contacted) and are derived deterministically from
            your declared profile. The wording layer may take a few seconds —
            if it is unavailable, a template explanation is used instead.
          </Alert>
        </div>

        <div className="mt-4">
          <ErrorBox error={runError} />
        </div>

        <PrimaryButton
          className="mt-2 w-full"
          loading={running}
          onClick={runAssessment}
        >
          {running ? "Assessing…" : "Run my assessment"}
        </PrimaryButton>
      </Card>
    </div>
  );
}
