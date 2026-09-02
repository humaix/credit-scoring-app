"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { api, type ConsentInfoResponse } from "@/lib/api";
import {
  Alert, Card, ErrorBox, PageSpinner, PrimaryButton, Stepper,
  useCurrentApplication,
} from "@/components/ui";

const CATEGORY_ORDER = [
  { key: "wallet_activity", title: "Mobile wallet activity" },
  { key: "telecom_activity", title: "Telecom activity" },
  { key: "digital_transactions", title: "Digital transactions" },
  { key: "previous_loan_info", title: "Previous loan information" },
] as const;

type Choices = Record<string, boolean>;

export default function ConsentPage() {
  const router = useRouter();
  const { app, loading, error } = useCurrentApplication("verified");

  const [info, setInfo] = useState<ConsentInfoResponse | null>(null);
  const [infoError, setInfoError] = useState<unknown>(null);
  const [choices, setChoices] = useState<Choices>({
    wallet_activity: true,
    telecom_activity: true,
    digital_transactions: true,
    previous_loan_info: true,
  });
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<unknown>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .get<ConsentInfoResponse>("/api/consent/info")
      .then((result) => {
        if (!cancelled) setInfo(result);
      })
      .catch((err) => {
        if (!cancelled) setInfoError(err);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (loading) return <PageSpinner />;
  if (error) {
    return (
      <div className="mx-auto max-w-md">
        <ErrorBox error={error} />
      </div>
    );
  }
  if (!app) return null;

  const allSelected = CATEGORY_ORDER.every(({ key }) => choices[key]);

  function toggle(key: string) {
    setChoices((prev) => ({ ...prev, [key]: !prev[key] }));
  }

  async function grantConsent() {
    setSubmitting(true);
    setSubmitError(null);
    try {
      await api.post("/api/consent", {
        application_id: app!.id,
        ...choices,
      });
      router.push("/assessment");
    } catch (err) {
      setSubmitError(err);
      setSubmitting(false);
    }
  }

  return (
    <div className="mx-auto max-w-xl">
      <Stepper current={2} />
      <Card>
        <h1 className="text-xl font-bold tracking-tight text-slate-900">
          Your data, your choice
        </h1>
        <p className="mt-1 text-sm text-slate-600">
          This assessment uses alternative data instead of a bank credit
          history. Select what you agree to share — nothing is accessed
          without your consent.
        </p>

        <div className="mt-5 space-y-3">
          {CATEGORY_ORDER.map(({ key, title }) => (
            <label
              key={key}
              className={`flex cursor-pointer items-start gap-3 rounded-xl border p-4 transition ${
                choices[key]
                  ? "border-[#0e9f6e] bg-emerald-50/60"
                  : "border-slate-200 bg-white"
              }`}
            >
              <input
                type="checkbox"
                className="mt-0.5 h-5 w-5 accent-[#0e9f6e]"
                checked={choices[key]}
                onChange={() => toggle(key)}
              />
              <span>
                <span className="block text-sm font-semibold text-slate-900">
                  {title}
                </span>
                <span className="mt-0.5 block text-xs leading-relaxed text-slate-600">
                  {info?.categories?.[key] ?? "—"}
                </span>
              </span>
            </label>
          ))}
        </div>

        {infoError ? (
          <div className="mt-4"><ErrorBox error={infoError} /></div>
        ) : null}

        {info && (
          <div className="mt-4">
            <Alert tone="warning">{info.notice}</Alert>
          </div>
        )}

        {!allSelected && (
          <div className="mt-3">
            <Alert tone="info">
              You have declined one or more categories. Assessment requires
              consent to all four — if you continue like this, no score can be
              produced for this application.
            </Alert>
          </div>
        )}

        <div className="mt-4">
          <ErrorBox error={submitError} />
        </div>

        <PrimaryButton
          className="mt-2 w-full"
          loading={submitting}
          disabled={!allSelected}
          onClick={grantConsent}
        >
          {allSelected ? "Grant consent and continue" : "Grant all categories to continue"}
        </PrimaryButton>
      </Card>
    </div>
  );
}
