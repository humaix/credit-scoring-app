"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import {
  api, currentAppId, displayName, formatDate, formatPKR, nextStepFor,
  setCurrentApp, type ApplicationSummary,
} from "@/lib/api";
import {
  Card, ErrorBox, PageSpinner, PrimaryButton, StatusBadge, useRequireSession,
} from "@/components/ui";

const CONTINUE_LABEL: Record<string, string> = {
  created: "Continue: verify identity",
  verified: "Continue: grant consent",
  consented: "Continue: take assessment",
  assessed: "Continue: run assessment",
  scored: "View results",
};

export default function DashboardPage() {
  const router = useRouter();
  const sessionReady = useRequireSession();
  const [applications, setApplications] = useState<ApplicationSummary[] | null>(null);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    if (!sessionReady) return;
    let cancelled = false;
    api
      .get<ApplicationSummary[]>("/api/applications")
      .then((rows) => {
        if (!cancelled) setApplications(rows);
      })
      .catch((err) => {
        if (!cancelled) setError(err);
      });
    return () => {
      cancelled = true;
    };
  }, [sessionReady]);

  if (!sessionReady) return null;
  if (error) {
    return (
      <div className="mx-auto max-w-2xl">
        <ErrorBox error={error} />
      </div>
    );
  }
  if (applications === null) return <PageSpinner />;

  const name = displayName();
  const activeId = currentAppId();

  function open(application: ApplicationSummary) {
    setCurrentApp(application.id);
    router.push(nextStepFor(application.status));
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div className="flex flex-col items-start justify-between gap-4 sm:flex-row sm:items-center">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">
            {name ? `Assalam-o-alaikum, ${name.split(" ")[0]}` : "Dashboard"}
          </h1>
          <p className="mt-1 text-sm text-slate-600">
            Your applications and assessments.
          </p>
        </div>
        <Link
          href="/apply"
          className="inline-flex h-10 items-center justify-center rounded-xl bg-[#0e9f6e] px-5 text-sm font-semibold text-white transition hover:bg-[#0b8a5e]"
        >
          New application
        </Link>
      </div>

      {applications.length === 0 ? (
        <Card className="text-center">
          <p className="text-sm text-slate-600">
            You haven&apos;t started an application yet.
          </p>
          <PrimaryButton className="mt-4" onClick={() => router.push("/apply")}>
            Start your first assessment
          </PrimaryButton>
        </Card>
      ) : (
        <ul className="space-y-3">
          {applications.map((application) => (
            <li key={application.id}>
              <Card
                className={`flex flex-col gap-4 !p-5 sm:flex-row sm:items-center sm:justify-between ${
                  application.id === activeId ? "ring-2 ring-[#0e9f6e]/40" : ""
                }`}
              >
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-sm font-bold text-slate-900">
                      Application #{application.id}
                    </span>
                    <StatusBadge status={application.status} />
                  </div>
                  <p className="mt-1 text-xs text-slate-500">
                    {application.occupation} · {formatPKR(application.requested_loan_size)} ·{" "}
                    {formatDate(application.created_at)}
                  </p>
                  {application.repayment_score !== null && (
                    <p className="mt-1.5 text-sm font-semibold text-[#0c2f48]">
                      Score: {application.repayment_score.toFixed(1)} / 100 ·{" "}
                      {application.score_category}
                    </p>
                  )}
                </div>
                <PrimaryButton
                  className="shrink-0"
                  onClick={() => open(application)}
                >
                  {CONTINUE_LABEL[application.status] ?? "Open"}
                </PrimaryButton>
              </Card>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
