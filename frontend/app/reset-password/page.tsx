"use client";

import { Suspense, useState, type FormEvent } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";

import { resetPassword } from "@/lib/api";
import {
  Alert, Card, ErrorBox, Field, PageSpinner, PrimaryButton, inputClass,
} from "@/components/ui";

const PASSWORD_HINT =
  "At least 8 characters, including at least one letter and one digit.";

function ResetPasswordForm() {
  const params = useSearchParams();
  const token = params.get("token");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (
      password.length < 8 ||
      !/[A-Za-z]/.test(password) ||
      !/\d/.test(password)
    ) {
      setFormError(`Password is too weak — ${PASSWORD_HINT.toLowerCase()}`);
      return;
    }
    if (password !== confirmPassword) {
      setFormError("Passwords do not match.");
      return;
    }
    setFormError(null);
    setLoading(true);
    setError(null);
    try {
      await resetPassword(token ?? "", password);
      setDone(true);
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }

  if (!token) {
    return (
      <Card>
        <h1 className="text-xl font-bold tracking-tight text-slate-900">
          Reset link problem
        </h1>
        <p className="mt-2 text-sm text-slate-600">
          This password-reset link is missing or incomplete. Request a new
          link and try again.
        </p>
        <p className="mt-5 text-center text-sm text-slate-600">
          <Link
            href="/forgot-password"
            className="font-semibold text-[#0e9f6e] hover:underline"
          >
            Request a new reset link
          </Link>
        </p>
      </Card>
    );
  }

  if (done) {
    return (
      <Card>
        <Alert tone="success">
          <p className="font-semibold">Password updated</p>
          <p className="mt-1">
            Your password has been changed and this reset link is no longer
            valid. Log in with your new password.
          </p>
        </Alert>
        <p className="mt-5 text-center text-sm text-slate-600">
          <Link href="/login" className="font-semibold text-[#0e9f6e] hover:underline">
            Go to login
          </Link>
        </p>
      </Card>
    );
  }

  return (
    <Card>
      <h1 className="text-xl font-bold tracking-tight text-slate-900">
        Set a new password
      </h1>
      <p className="mt-1 text-sm text-slate-600">
        Choose a new password for your account.
      </p>

      <form className="mt-6 space-y-4" onSubmit={onSubmit}>
        <Field label="New password" hint={PASSWORD_HINT}>
          <div className="relative">
            <input
              className={`${inputClass} pr-14`}
              type={showPassword ? "text" : "password"}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="new-password"
              minLength={8}
              maxLength={128}
              required
            />
            <button
              type="button"
              onClick={() => setShowPassword((visible) => !visible)}
              className="absolute inset-y-0 right-0 flex items-center px-3 text-xs font-semibold text-slate-500 transition hover:text-slate-700"
              aria-label={showPassword ? "Hide password" : "Show password"}
            >
              {showPassword ? "Hide" : "Show"}
            </button>
          </div>
        </Field>

        <Field label="Confirm new password">
          <input
            className={inputClass}
            type="password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            autoComplete="new-password"
            maxLength={128}
            required
          />
        </Field>

        <ErrorBox error={error} />
        {formError && !error && (
          <Alert tone="error">
            <p className="font-medium">{formError}</p>
          </Alert>
        )}

        <PrimaryButton type="submit" loading={loading} className="w-full">
          Update password
        </PrimaryButton>
      </form>
    </Card>
  );
}

export default function ResetPasswordPage() {
  return (
    <div className="mx-auto max-w-md">
      <Suspense fallback={<PageSpinner />}>
        <ResetPasswordForm />
      </Suspense>
    </div>
  );
}
