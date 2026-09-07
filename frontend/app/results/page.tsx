"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import {
  downloadReport, formatPKR,
  type FeatureInterpretation, type ContributorBlock,
} from "@/lib/api";
import ContributionChart from "@/components/ContributionChart";
import ScoreGauge from "@/components/ScoreGauge";
import {
  Alert, Card, ErrorBox, PageSpinner, PrimaryButton, SecondaryButton,
  StatusBadge, Stepper, useCurrentApplication,
} from "@/components/ui";

function IndicatorCard({ item }: { item: FeatureInterpretation }) {
  const hasDetails = Boolean(item.components && item.components.length > 0) || Boolean(item.how_calculated);

  return (
    <div className="rounded-xl border border-slate-200 bg-slate-50/50 p-4 transition hover:bg-slate-50">
      <div className="flex items-start justify-between gap-2">
        <div>
          <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
            {item.label}
          </span>
          <div className="mt-1 flex items-baseline gap-2">
            <span className="text-xl font-bold text-slate-900">{item.value}</span>
            {item.band && (
              <span className="rounded-full bg-slate-200/80 px-2 py-0.5 text-xs font-medium text-slate-700">
                {item.band}
              </span>
            )}
          </div>
        </div>
      </div>

      {item.meaning && (
        <p className="mt-2 text-xs leading-relaxed text-slate-600">
          {item.meaning}
        </p>
      )}

      {item.reference_note && (
        <p className="mt-1.5 text-xs font-medium text-slate-500 italic">
          {item.reference_note}
        </p>
      )}

      {hasDetails && (
        <details className="group mt-3 rounded-lg border border-slate-200 bg-white text-xs">
          <summary className="flex cursor-pointer items-center justify-between p-2.5 font-medium text-slate-700 hover:text-[#0e9f6e]">
            <span>How was this calculated?</span>
            <span className="text-slate-400 group-open:rotate-180 transition-transform">▼</span>
          </summary>
          <div className="border-t border-slate-100 p-3 space-y-2">
            {item.formula && (
              <div className="font-mono text-[11px] text-slate-600 bg-slate-50 p-2 rounded">
                Formula: {item.formula}
              </div>
            )}
            {item.components && item.components.length > 0 && (
              <div className="space-y-1.5 pt-1">
                {item.components.map((c, i) => (
                  <div key={i} className="flex items-start justify-between gap-2 text-slate-600 border-b border-slate-50 pb-1 last:border-0">
                    <div>
                      <span className="font-medium text-slate-800">{c.name}</span>{" "}
                      <span className="text-slate-400">({c.weight})</span>
                      <p className="text-[11px] text-slate-500">{c.description}</p>
                    </div>
                    <span className="font-semibold text-slate-700">{c.score}</span>
                  </div>
                ))}
              </div>
            )}
            {item.how_calculated && !item.formula && (
              <p className="text-slate-600">{item.how_calculated}</p>
            )}
            {item.simulation_note && (
              <p className="pt-1 text-[11px] text-amber-700 italic border-t border-slate-100">
                {item.simulation_note}
              </p>
            )}
          </div>
        </details>
      )}
    </div>
  );
}

function ContributorList({
  title,
  contributors,
  fallbackItems,
  tone,
}: {
  title: string;
  contributors?: ContributorBlock[];
  fallbackItems: string[];
  tone: "positive" | "negative";
}) {
  const isPositive = tone === "positive";

  if (contributors && contributors.length > 0) {
    return (
      <div className="rounded-2xl border border-slate-200 bg-white p-5">
        <h3 className={`text-sm font-bold ${isPositive ? "text-emerald-700" : "text-red-700"}`}>
          {title}
        </h3>
        <div className="mt-3 space-y-3">
          {contributors.map((item, index) => (
            <div
              key={index}
              className={`rounded-xl border p-3.5 text-xs leading-relaxed ${
                isPositive ? "border-emerald-100 bg-emerald-50/40" : "border-red-100 bg-red-50/40"
              }`}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="font-bold text-slate-900">
                  {item.feature}: <span className="font-semibold text-slate-700">{item.value}</span>
                </span>
                <span className={`font-bold ${isPositive ? "text-emerald-600" : "text-red-600"}`}>
                  {isPositive ? "▲ Positive" : "▼ Negative"}
                </span>
              </div>
              {item.meaning && (
                <p className="mt-1.5 text-slate-600">{item.meaning}</p>
              )}
              {item.influence && (
                <p className={`mt-1 font-medium ${isPositive ? "text-emerald-800" : "text-red-800"}`}>
                  {item.influence}
                </p>
              )}
              {item.reference_note && (
                <p className="mt-1 text-[11px] text-slate-500 italic">
                  {item.reference_note}
                </p>
              )}
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5">
      <h3 className={`text-sm font-bold ${isPositive ? "text-emerald-700" : "text-red-700"}`}>
        {title}
      </h3>
      {fallbackItems.length === 0 ? (
        <p className="mt-2 text-xs text-slate-500">
          {isPositive
            ? "No features meaningfully raised the score."
            : "No features meaningfully reduced the score."}
        </p>
      ) : (
        <ul className="mt-2 space-y-2">
          {fallbackItems.map((item, index) => (
            <li key={index} className="flex gap-2 text-xs leading-relaxed text-slate-700">
              <span className={`mt-0.5 font-bold ${isPositive ? "text-emerald-600" : "text-red-600"}`}>
                {isPositive ? "▲" : "▼"}
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
  const interpretation = assessment.interpretation;

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

  const creditData = interpretation?.credit_history;

  return (
    <div className="space-y-6">
      <Stepper current={5} />

      {/* 1. Score Summary */}
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
        <p className="mt-6 text-center text-xs text-slate-600 border-t border-slate-100 pt-4">
          Your score reflects the combined influence of your financial, credit-history,
          loan-request, digital-activity and behavioral information.
        </p>
      </Card>

      <Alert tone="warning">
        <strong>Important:</strong> This score is a model-estimated repayment
        assessment and is not a guaranteed probability of repayment or an
        automatic loan approval decision. Loan decisions remain with the
        lending institution.
      </Alert>

      {/* 2. Credit History Verification (Expandable) */}
      {creditData && (
        <Card>
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
            <div>
              <h2 className="text-base font-bold tracking-tight text-slate-900">
                Credit History Verification
              </h2>
              <p className="mt-0.5 text-xs text-slate-500">
                Verified classification from credit-information indicators
              </p>
            </div>
            <span className="inline-flex items-center rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-800 border border-emerald-200">
              {creditData.derived_loan_history}
            </span>
          </div>

          <p className="mt-3 text-xs leading-relaxed text-slate-700">
            {creditData.explanation.narrative}
          </p>

          <details className="group mt-4 rounded-xl border border-slate-200 bg-slate-50/50 text-xs">
            <summary className="flex cursor-pointer items-center justify-between p-3 font-medium text-slate-700 hover:text-[#0e9f6e]">
              <span>View verification details</span>
              <span className="text-slate-400 group-open:rotate-180 transition-transform">▼</span>
            </summary>
            <div className="border-t border-slate-200 p-4 bg-white rounded-b-xl space-y-3">
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                {creditData.explanation.rows.map((row, idx) => (
                  <div key={idx} className="rounded-lg bg-slate-50 p-2.5">
                    <span className="text-[11px] text-slate-500 block">{row.label}</span>
                    <span className="font-semibold text-slate-800">{row.value}</span>
                  </div>
                ))}
              </div>
              <p className="text-[11px] text-amber-700 italic border-t border-slate-100 pt-2">
                {creditData.demo_notice}
              </p>
            </div>
          </details>
        </Card>
      )}

      {/* 3. Financial Indicators */}
      {interpretation?.financial_indicators && (
        <Card>
          <h2 className="text-base font-bold tracking-tight text-slate-900">
            Your Financial Indicators
          </h2>
          <p className="mt-0.5 text-xs text-slate-500">
            Declared financial profile compared with training reference distributions
          </p>
          <div className="mt-4 grid gap-3 sm:grid-cols-3">
            {interpretation.financial_indicators.map((item, idx) => (
              <IndicatorCard key={idx} item={item} />
            ))}
          </div>
        </Card>
      )}

      {/* 4. Digital & Behavioral Indicators */}
      {interpretation?.digital_indicators && (
        <Card>
          <h2 className="text-base font-bold tracking-tight text-slate-900">
            Your Digital &amp; Behavioral Indicators
          </h2>
          <p className="mt-0.5 text-xs text-slate-500">
            Alternative data composites and financial behavior assessment
          </p>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            {interpretation.digital_indicators.map((item, idx) => (
              <IndicatorCard key={idx} item={item} />
            ))}
          </div>
        </Card>
      )}

      {/* 5. What Supported & What Reduced Score */}
      <Card>
        <h2 className="text-base font-bold tracking-tight text-slate-900">
          Why this score
        </h2>
        <p className="mt-1 text-xs leading-relaxed text-slate-700">
          {assessment.explanation.summary}
        </p>
        <div className="mt-5 grid gap-4 md:grid-cols-2">
          <ContributorList
            title="What supported your score"
            contributors={interpretation?.top_supported}
            fallbackItems={assessment.explanation.positive_factors}
            tone="positive"
          />
          <ContributorList
            title="What reduced your score"
            contributors={interpretation?.top_reduced}
            fallbackItems={assessment.explanation.negative_factors}
            tone="negative"
          />
        </div>
        <p className="mt-4 text-xs leading-relaxed text-slate-600">
          {assessment.explanation.overall_explanation}
        </p>
      </Card>

      {/* 6. How the Final Score Was Generated */}
      <Card>
        <h2 className="text-base font-bold tracking-tight text-slate-900">
          How the Final Score Was Generated
        </h2>
        <div className="mt-4 rounded-xl border border-slate-200 bg-slate-50 p-4">
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 text-center text-xs">
            <div className="rounded-lg bg-white p-3 border border-slate-200 shadow-sm">
              <span className="font-bold text-slate-800 block">Financial Data</span>
              <span className="text-[11px] text-slate-500">Income &amp; debt burden</span>
            </div>
            <div className="rounded-lg bg-white p-3 border border-slate-200 shadow-sm">
              <span className="font-bold text-slate-800 block">Credit History</span>
              <span className="text-[11px] text-slate-500">Verified record</span>
            </div>
            <div className="rounded-lg bg-white p-3 border border-slate-200 shadow-sm">
              <span className="font-bold text-slate-800 block">Digital Activity</span>
              <span className="text-[11px] text-slate-500">Telecom &amp; wallet</span>
            </div>
            <div className="rounded-lg bg-white p-3 border border-slate-200 shadow-sm">
              <span className="font-bold text-slate-800 block">Behavioral Assessment</span>
              <span className="text-[11px] text-slate-500">12 survey dimensions</span>
            </div>
          </div>
          <div className="my-2 text-center text-slate-400 font-bold">↓</div>
          <div className="rounded-lg bg-[#0c2f48] p-3 text-center text-white text-xs font-semibold">
            Trained XGBoost Repayment Model (considers all inputs together)
          </div>
          <div className="my-2 text-center text-slate-400 font-bold">↓</div>
          <div className="rounded-lg bg-emerald-600 p-3 text-center text-white text-sm font-bold">
            Repayment Score: {assessment.repayment_score.toFixed(1)} / 100 ({assessment.score_category})
          </div>
        </div>
        <p className="mt-3 text-xs text-slate-500 italic">
          {interpretation?.pipeline_note ||
            "The scoring model considers all of these inputs together — the categories above are not manually added up to produce your score."}
        </p>
      </Card>

      {/* 7. Collapsible Technical Attribution (SHAP Details) */}
      <Card>
        <details className="group">
          <summary className="flex cursor-pointer items-center justify-between text-sm font-bold text-slate-800 hover:text-[#0e9f6e]">
            <span>Technical Details (Feature Contributions)</span>
            <span className="text-xs font-normal text-slate-400 group-open:rotate-180 transition-transform">▼</span>
          </summary>
          <div className="mt-4 border-t border-slate-100 pt-4">
            <p className="text-xs text-slate-500 mb-3">
              Model baseline: {assessment.base_value.toFixed(1)} points. Each bar shows how
              individual features shifted the score from the baseline.
            </p>
            <ContributionChart contributions={assessment.all_contributions} />
          </div>
        </details>
      </Card>

      {/* 8. Assessment notes if any */}
      {app.questionnaire && app.questionnaire.consistency_warnings.length > 0 && (
        <Card>
          <h2 className="text-sm font-bold tracking-tight text-slate-900">
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

      {/* 9. Report Action */}
      <Card>
        <div className="flex flex-col items-center justify-between gap-4 sm:flex-row">
          <div>
            <h2 className="text-base font-bold tracking-tight text-slate-900">
              Your report
            </h2>
            <p className="mt-1 text-xs text-slate-600">
              Download the complete PDF report with all explanations and reference notes.
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
