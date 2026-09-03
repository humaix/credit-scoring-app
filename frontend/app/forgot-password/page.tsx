"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";

import { requestPasswordReset, type ForgotPasswordResponse } from "@/lib/api";
import { Alert, Card, ErrorBox, Field, PrimaryButton, inputClass } from "@/components/ui";

export default function ForgotPasswordPage() {
  const [cnic, setCnic] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [result, setResult] = useState<ForgotPasswordResponse | null>(null);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      setResult(await requestPasswordReset(cnic.trim()));
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }

  if (result) {
    return (
      <div className="mx-auto max-w-md">
        <Card>
          <h1 className="text-xl font-bold tracking-tight text-slate-900">
            Check your email
          </h1>
          <p className="mt-2 text-sm text-slate-600">{result.message}</p>
          <p className="mt-2 text-sm text-slate-600">
            The link expires shortly and can only be used once. If it
            doesn&apos;t arrive, check your spam folder — then request a new
            link.
          </p>

          {result.dev_reset_url && (
            <div className="mt-4">
              <Alert tone="warning">
                <p className="font-semibold">Development mode</p>
                <p className="mt-1">{result.dev_notice}</p>
                <Link
                  href={result.dev_reset_url}
                  className="mt-2 inline-block font-semibold text-amber-900 underline"
                >
                  Open the password-reset link
                </Link>
              </Alert>
            </div>
          )}

          <p className="mt-5 text-center text-sm text-slate-600">
            <Link href="/login" className="font-semibold text-[#0e9f6e] hover:underline">
              Back to login
            </Link>
          </p>
        </Card>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-md">
      <Card>
        <h1 className="text-xl font-bold tracking-tight text-slate-900">
          Forgot your password?
        </h1>
        <p className="mt-1 text-sm text-slate-600">
          Enter the CNIC you registered with. If an account exists, we&apos;ll
          email a password-reset link to the address on file.
        </p>

        <form className="mt-6 space-y-4" onSubmit={onSubmit}>
          <Field
            label="CNIC"
            hint="Format: XXXXX-XXXXXXX-X, e.g. 35202-1234567-1"
          >
            <input
              className={inputClass}
              value={cnic}
              onChange={(e) => setCnic(e.target.value)}
              placeholder="35202-1234567-1"
              autoComplete="off"
              required
            />
          </Field>

          <ErrorBox error={error} />

          <PrimaryButton type="submit" loading={loading} className="w-full">
            Send reset link
          </PrimaryButton>
        </form>

        <p className="mt-5 text-center text-sm text-slate-600">
          Remembered it?{" "}
          <Link href="/login" className="font-semibold text-[#0e9f6e] hover:underline">
            Back to login
          </Link>
        </p>
      </Card>
    </div>
  );
}
