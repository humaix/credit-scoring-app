"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import { api, type OtpRequestResult, type OtpVerifyResult } from "@/lib/api";
import {
  Alert, Card, ErrorBox, Field, PageSpinner, PrimaryButton, SecondaryButton,
  Stepper, inputClass, useCurrentApplication,
} from "@/components/ui";

export default function VerifyPage() {
  const router = useRouter();
  const { app, loading, error } = useCurrentApplication("created");

  const [otpSent, setOtpSent] = useState(false);
  const [simulatedOtp, setSimulatedOtp] = useState<string | null>(null);
  const [expiresIn, setExpiresIn] = useState<number | null>(null);
  const [code, setCode] = useState("");
  const [verifying, setVerifying] = useState(false);
  const [sending, setSending] = useState(false);
  const [requestError, setRequestError] = useState<unknown>(null);
  const [feedback, setFeedback] = useState<string | null>(null);

  if (loading) return <PageSpinner />;
  if (error) {
    return (
      <div className="mx-auto max-w-md">
        <ErrorBox error={error} />
      </div>
    );
  }
  if (!app) return null;

  async function sendOtp() {
    setSending(true);
    setRequestError(null);
    setFeedback(null);
    try {
      const result = await api.post<OtpRequestResult>(
        "/api/verification/request-otp",
        { application_id: app!.id },
      );
      setOtpSent(true);
      setSimulatedOtp(result.simulated_otp ?? null);
      setExpiresIn(result.expires_in_seconds);
    } catch (err) {
      setRequestError(err);
    } finally {
      setSending(false);
    }
  }

  async function verifyOtp() {
    setVerifying(true);
    setRequestError(null);
    setFeedback(null);
    try {
      const result = await api.post<OtpVerifyResult>(
        "/api/verification/verify-otp",
        { application_id: app!.id, code: code.trim() },
      );
      if (result.status === "verified") {
        // Phase 3: the employment/document step runs between identity
        // verification and consent
        router.push("/employment");
        return;
      }
      if (result.status === "pending") {
        setFeedback(
          `${result.message ?? "Incorrect code."} ${
            result.attempts_remaining ?? 0
          } attempt(s) remaining.`,
        );
      } else {
        setFeedback(
          `${result.message ?? "Verification failed."} You can request a new code.`,
        );
        setOtpSent(false);
        setSimulatedOtp(null);
      }
    } catch (err) {
      setRequestError(err);
    } finally {
      setVerifying(false);
    }
  }

  return (
    <div className="mx-auto max-w-md">
      <Stepper current={1} />
      <Card>
        <h1 className="text-xl font-bold tracking-tight text-slate-900">
          Identity verification
        </h1>
        <p className="mt-1 text-sm text-slate-600">
          We&apos;ll send a one-time code to your registered mobile number to
          confirm you own it.
        </p>

        <div className="mt-5 space-y-1 rounded-xl bg-slate-50 p-4 text-sm">
          <div className="flex justify-between">
            <span className="text-slate-500">Name</span>
            <span className="font-medium text-slate-900">
              {app.applicant.full_name}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-500">CNIC</span>
            <span className="font-mono font-medium text-slate-900">
              {app.applicant.cnic_masked}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-500">Mobile</span>
            <span className="font-mono font-medium text-slate-900">
              {app.applicant.mobile_masked}
            </span>
          </div>
        </div>

        {!otpSent ? (
          <div className="mt-6">
            <Alert tone="info">
              <strong>Simulated verification.</strong> No real SMS is sent —
              this prototype has no NADRA or telecom integration. In demo mode
              the code is shown directly on screen.
            </Alert>
            <ErrorBox error={requestError} />
            <PrimaryButton
              className="mt-4 w-full"
              loading={sending}
              onClick={sendOtp}
            >
              Send verification code
            </PrimaryButton>
          </div>
        ) : (
          <div className="mt-6 space-y-4">
            {simulatedOtp && (
              <Alert tone="warning">
                <p className="font-semibold">
                  Demo mode — your simulated code is:
                </p>
                <p className="mt-1 select-all font-mono text-2xl font-bold tracking-[0.3em]">
                  {simulatedOtp}
                </p>
                {expiresIn !== null && (
                  <p className="mt-1 text-xs">
                    Expires in {Math.round(expiresIn / 60)} minutes.
                  </p>
                )}
              </Alert>
            )}

            <Field label="Enter the 6-digit code">
              <input
                className={`${inputClass} text-center font-mono text-lg tracking-[0.3em]`}
                value={code}
                onChange={(e) => setCode(e.target.value)}
                placeholder="••••••"
                inputMode="numeric"
                maxLength={8}
                autoComplete="one-time-code"
              />
            </Field>

            {feedback && <Alert tone="warning">{feedback}</Alert>}
            <ErrorBox error={requestError} />

            <PrimaryButton
              className="w-full"
              loading={verifying}
              disabled={code.trim().length < 4}
              onClick={verifyOtp}
            >
              Verify code
            </PrimaryButton>
            <SecondaryButton className="w-full" onClick={sendOtp} disabled={sending}>
              Resend code
            </SecondaryButton>
          </div>
        )}
      </Card>
    </div>
  );
}
