"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import { submitEmployment, type EmploymentSubmitResult } from "@/lib/api";
import CameraCapture from "@/components/CameraCapture";
import {
  Alert, Card, ErrorBox, Field, PageSpinner, PrimaryButton, Stepper,
  inputClass, useCurrentApplication,
} from "@/components/ui";

const BUSINESS_OCCUPATIONS = ["Business Owner", "Self-Employed"];

export default function EmploymentPage() {
  const router = useRouter();
  const { app, loading, error } = useCurrentApplication("verified", {
    employment: "absent",
  });

  const [employerName, setEmployerName] = useState("");
  const [businessName, setBusinessName] = useState("");
  // null = untouched; the prefilled re-confirmed income is derived below so
  // no setState happens inside an effect
  const [declaredIncome, setDeclaredIncome] = useState<string | null>(null);
  const [documentImage, setDocumentImage] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<unknown>(null);
  const [result, setResult] = useState<EmploymentSubmitResult | null>(null);

  if (loading) return <PageSpinner />;
  if (error) {
    return (
      <div className="mx-auto max-w-md">
        <ErrorBox error={error} />
      </div>
    );
  }
  if (!app) return null;

  const isSalaried = app.occupation === "Salaried";
  const isBusiness = BUSINESS_OCCUPATIONS.includes(app.occupation);
  // business applicants re-confirm the income they declared when applying
  // (prefilled until they edit it); salaried applicants enter their salary
  // fresh — it can differ from the total income the application captured
  const incomeField =
    declaredIncome ?? (isBusiness ? String(app.monthly_income) : "");
  // the bank statement exists only for business applicants WITH a bank
  // account — everyone else proceeds on alternative data
  const needsDocument = isSalaried || (isBusiness && app.has_bank_account);
  const documentLabel = isSalaried ? "Salary slip" : "Bank statement";

  const incomeValue = Number(incomeField);
  const incomeValid =
    incomeField !== "" && Number.isFinite(incomeValue) && incomeValue > 0;
  const incomeInvalid = incomeField !== "" && !incomeValid;

  const textValid = isSalaried
    ? employerName.trim().length >= 2
    : isBusiness
      ? businessName.trim().length >= 2
      : true;
  const canSubmit =
    (needsDocument ? documentImage !== null : true) && textValid && (
      isSalaried || isBusiness ? incomeValid : true
    );

  const buttonLabel = !needsDocument
    ? "Continue"
    : documentImage === null
      ? `Capture your ${documentLabel.toLowerCase()} to continue`
      : !textValid || (isSalaried || isBusiness) && !incomeValid
        ? "Complete the required details"
        : "Submit and continue";

  async function onSubmit() {
    setSubmitting(true);
    setSubmitError(null);
    try {
      const response = await submitEmployment(app!.id, {
        ...(isSalaried ? { employer_name: employerName.trim() } : {}),
        ...(isBusiness ? { business_name: businessName.trim() } : {}),
        ...(isSalaried || isBusiness ? { declared_income: incomeValue } : {}),
        ...(needsDocument && documentImage
          ? { document_image: documentImage }
          : {}),
      });
      setResult(response);
    } catch (err) {
      setSubmitError(err);
    } finally {
      setSubmitting(false);
    }
  }

  if (result) {
    return (
      <div className="mx-auto max-w-xl">
        <Stepper current={2} />
        <Card>
          <h1 className="text-xl font-bold tracking-tight text-slate-900">
            Employment verification submitted
          </h1>
          <div className="mt-4 flex items-center gap-3 rounded-xl border border-slate-200 bg-slate-50 p-4">
            <span
              className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-semibold ${
                result.status === "needs_review"
                  ? "bg-amber-100 text-amber-800"
                  : "bg-slate-100 text-slate-700"
              }`}
            >
              {result.status_label}
            </span>
            <span className="text-sm text-slate-600">
              {result.doc_type === "salary_slip"
                ? "Salary slip captured"
                : result.doc_type === "bank_statement"
                  ? "Bank statement captured"
                  : "No document required"}
            </span>
          </div>

          <div className="mt-4">
            <Alert tone="warning">{result.notice}</Alert>
          </div>

          {result.checks.length > 0 && (
            <div className="mt-5">
              <h2 className="text-sm font-bold text-slate-900">
                Prototype checks performed
              </h2>
              <ul className="mt-2 space-y-2">
                {result.checks.map((check) => (
                  <li
                    key={check.check}
                    className="flex items-start gap-2 rounded-xl border border-slate-200 p-3 text-xs leading-relaxed"
                  >
                    <span
                      className={`mt-0.5 font-bold ${
                        check.result === "flag" ? "text-amber-600" : "text-emerald-600"
                      }`}
                    >
                      {check.result === "flag" ? "⚑" : "✓"}
                    </span>
                    <span className="text-slate-700">
                      <span className="font-semibold">
                        {check.check.replace(/_/g, " ")}
                      </span>
                      {" — "}
                      {check.detail}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          <PrimaryButton
            className="mt-6 w-full"
            onClick={() => router.push("/consent")}
          >
            Continue to consent
          </PrimaryButton>
        </Card>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-xl">
      <Stepper current={2} />
      <Card>
        <h1 className="text-xl font-bold tracking-tight text-slate-900">
          Employment &amp; income verification
        </h1>
        <p className="mt-1 text-sm text-slate-600">
          Tell us about your work{needsDocument ? " and capture the document that supports it" : ""}.
        </p>

        <div className="mt-5 space-y-1 rounded-xl bg-slate-50 p-4 text-sm">
          <div className="flex justify-between">
            <span className="text-slate-500">Occupation</span>
            <span className="font-medium text-slate-900">{app.occupation}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-500">Bank account</span>
            <span className="font-medium text-slate-900">
              {app.has_bank_account ? app.bank_name : "None declared"}
            </span>
          </div>
        </div>

        <div className="mt-4">
          <Alert tone="info">
            <strong>Document-Based Prototype Verification.</strong> This
            prototype performs no OCR and no employer or bank verification —
            a captured document is quality-checked and marked{" "}
            <em>Pending Provider Verification</em>. Reading a document would
            not prove it authentic anyway.
          </Alert>
        </div>

        {isSalaried && (
          <div className="mt-5 space-y-4">
            <Field label="Employer name" hint="The company or organization that pays your salary.">
              <input
                className={inputClass}
                value={employerName}
                onChange={(e) => setEmployerName(e.target.value)}
                placeholder="e.g. Systems Limited"
                maxLength={100}
              />
            </Field>
            <Field label="Monthly salary (PKR)" hint="Your gross monthly salary as shown on your slip.">
              <input
                className={inputClass}
                value={incomeField}
                onChange={(e) => setDeclaredIncome(e.target.value)}
                placeholder="e.g. 60000"
                inputMode="numeric"
              />
            </Field>
          </div>
        )}

        {isBusiness && (
          <div className="mt-5 space-y-4">
            <Field label="Business name" hint="Your registered business or trade name.">
              <input
                className={inputClass}
                value={businessName}
                onChange={(e) => setBusinessName(e.target.value)}
                placeholder="e.g. Raza Traders"
                maxLength={100}
              />
            </Field>
            <Field
              label="Declared monthly income (PKR)"
              hint="Confirm or correct the income you declared when applying — checked for consistency only."
            >
              <input
                className={inputClass}
                value={incomeField}
                onChange={(e) => setDeclaredIncome(e.target.value)}
                inputMode="numeric"
              />
            </Field>
          </div>
        )}

        {needsDocument && (
          <div className="mt-5">
            <CameraCapture
              label={documentLabel}
              hint={
                isSalaried
                  ? "Capture your most recent salary slip — or upload it if you have it as a file."
                  : "Capture a recent bank statement page — or upload it if you have it as a file."
              }
              value={documentImage}
              onChange={setDocumentImage}
            />
          </div>
        )}

        {!isSalaried && !isBusiness && (
          <div className="mt-4">
            <Alert tone="info">
              No employment document is applicable for your occupation —
              your assessment proceeds on alternative data. Nothing to
              capture here; just continue.
            </Alert>
          </div>
        )}

        {isBusiness && !app.has_bank_account && (
          <div className="mt-4">
            <Alert tone="info">
              No bank statement is required because you did not declare a
              bank account — your assessment proceeds on alternative data.
            </Alert>
          </div>
        )}

        {incomeInvalid && (
          <div className="mt-3">
            <Alert tone="error">
              Enter a valid monthly amount greater than zero.
            </Alert>
          </div>
        )}

        <div className="mt-4">
          <ErrorBox error={submitError} />
        </div>

        <PrimaryButton
          className="mt-2 w-full"
          loading={submitting}
          disabled={!canSubmit}
          onClick={onSubmit}
        >
          {buttonLabel}
        </PrimaryButton>
      </Card>
    </div>
  );
}
