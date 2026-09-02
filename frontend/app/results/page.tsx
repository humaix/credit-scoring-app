"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { api, downloadReport, formatPKR } from "@/lib/api";
import ContributionChart from "@/components/ContributionChart";
import ScoreGauge from "@/components/ScoreGauge";
import {
  Alert, Card, ErrorBox, PageSpinner, PrimaryButton, SecondaryButton,
  StatusBadge, Stepper, useCurrentApplication,
} from "@/components/ui";

function FactorList({
  title,
  items,
  tone,
}: {
  title: string;
  items: string[];
  tone: "positive" | "negative";
}) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5">
      <h3
        className={`text-sm font-bold ${
          tone === "positive" ? "text-emerald-700" : "text-red-700"
        }`}
      >
        {title}
      </h3>
      {items.length === 0 ? (
        <p className="mt-2 text-xs text-slate-500">
          {tone === "positive"
            ? "No features meaningfully raised the score."
            : "No features meaningfully reduced the score."}
        </p>
      ) : (
        <ul className="mt-2 space-y-2">
          {items.map((item, index) => (
            <li key={index} className="flex gap-2 text-xs leading-relaxed text-slate-700">
              <span
                className={`mt-0.5 font-bold ${
                  tone === "positive" ? "text-emerald-600" : "text-red-600"
                }`}
              >
                {tone === "positive" ? "▲" : "▼"}
              </span>
              {item}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default function ResultsPage() {
  const router = useRouter();
  const { app, loading, error } = useCurrentApplication("scored");
  const [downloading, setDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState<unknown>(null);

  if (loading) return <PageSpinner />;
  if (error) {
    return (
      <div className="mx-auto max-w-md">
        <ErrorBox error={error} />
      </div>
    );
  }
  if (!app || !app.assessment) return null;

  const applicationId = app.id;
  const assessment = app.assessment;

  async function onDownload() {
    setDownloading(true);
    setDownloadError(null);
    try {
      await downloadReport(applicationId);
    } catch (err) {
      setDownloadError(err);
    } finally {
      setDownloading(false);
    }
  }

  return (
    <div className="space-y-6">
      <Stepper current={4} />

      <Card className="rise-in">
        <div className="flex flex-col items-center gap-8 sm:flex-row sm:justify-around">
          <ScoreGauge
            score={assessment.repayment_score}
            category={assessment.score_category}
          />
          <div className="max-w-sm space-y-3 text-sm">
            <div className="flex justify-between gap-6">
              <span className="text-slate-500">Application</span>
              <span className="font-semibold text-slate-900">#{app.id}</span>
            </div>
            <div className="flex justify-between gap-6">
              <span className="text-slate-500">Requested loan</span>
              <span className="font-semibold text-slate-900">
                {formatPKR(app.requested_loan_size)}
              </span>
            </div>
            <div className="flex justify-between gap-6">
              <span className="text-slate-500">Assessment status</span>
              <StatusBadge status={app.status} />
            </div>
            <div className="flex justify-between gap-6">
              <span className="text-slate-500">Identity verification</span>
              <span className="font-semibold text-emerald-700">
                {app.verification?.status === "verified"
                  ? "Verified (simulated)"
                  : app.verification?.status ?? "—"}
              </span>
            </div>
            <div className="flex justify-between gap-6">
              <span className="text-slate-500">Explanation source</span>
              <span className="font-semibold text-slate-900">
                {assessment.explanation_source === "llm"
                  ? "AI wording layer"
                  : "Standard templates"}
              </span>
            </div>
          </div>
        </div>
      </Card>

      <Alert tone="warning">
        <strong>Important:</strong> This score is a model-estimated repayment
        assessment and is not a guaranteed probability of repayment or an
        automatic loan approval decision. Loan decisions remain with the
        lending institution.
      </Alert>

      <Card>
        <h2 className="text-lg font-bold tracking-tight text-slate-900">
          Why this score
        </h2>
        <p className="mt-2 text-sm leading-relaxed text-slate-700">
          {assessment.explanation.summary}
        </p>
        <div className="mt-5 grid gap-4 md:grid-cols-2">
          <FactorList
            title="What helped"
            items={assessment.explanation.positive_factors}
            tone="positive"
          />
          <FactorList
            title="What worked against"
            items={assessment.explanation.negative_factors}
            tone="negative"
          />
        </div>
        <p className="mt-4 text-sm leading-relaxed text-slate-700">
          {assessment.explanation.overall_explanation}
        </p>
      </Card>

      <Card>
        <h2 className="text-lg font-bold tracking-tight text-slate-900">
          How each factor moved the score
        </h2>
        <p className="mt-1 text-xs text-slate-500">
          Model baseline {assessment.base_value.toFixed(1)} points; contributions
          add up to the final estimate.
        </p>
        <div className="mt-5">
          <ContributionChart contributions={assessment.all_contributions} />
        </div>
      </Card>

      {app.questionnaire && app.questionnaire.consistency_warnings.length > 0 && (
        <Card>
          <h2 className="text-lg font-bold tracking-tight text-slate-900">
            Assessment notes
          </h2>
          <div className="mt-3">
            <Alert tone="warning">
              <ul className="list-inside list-disc space-y-1 text-xs">
                {app.questionnaire.consistency_warnings.map((warning) => (
                  <li key={warning}>{warning}</li>
                ))}
              </ul>
              <p className="mt-1.5 text-xs">
                Consistency indicators are flagged for manual review only —
                they never change the score.
              </p>
            </Alert>
          </div>
        </Card>
      )}

      <Card>
        <div className="flex flex-col items-center justify-between gap-4 sm:flex-row">
          <div>
            <h2 className="text-lg font-bold tracking-tight text-slate-900">
              Your report
            </h2>
            <p className="mt-1 text-sm text-slate-600">
              Download the full PDF — same score, same factors, same
              disclaimer.
            </p>
          </div>
          <div className="flex gap-3">
            <PrimaryButton loading={downloading} onClick={onDownload}>
              Download PDF report
            </PrimaryButton>
          </div>
        </div>
        <div className="mt-4">
          <ErrorBox error={downloadError} />
        </div>
        <div className="mt-2 flex justify-center sm:justify-end">
          <SecondaryButton onClick={() => router.push("/dashboard")}>
            Go to dashboard
          </SecondaryButton>
        </div>
      </Card>

      <p className="text-center text-xs text-slate-500">
        Need to run another assessment?{" "}
        <Link href="/apply" className="font-semibold text-[#0e9f6e] hover:underline">
          Start a new application
        </Link>
      </p>
    </div>
  );
}
