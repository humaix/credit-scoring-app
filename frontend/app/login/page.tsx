"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { api, clearCurrentApp, saveSession, type LoginResponse } from "@/lib/api";
import { Card, ErrorBox, Field, PrimaryButton, inputClass } from "@/components/ui";

export default function LoginPage() {
  const router = useRouter();
  const [cnic, setCnic] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [remember, setRemember] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<unknown>(null);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const result = await api.post<LoginResponse>("/api/auth/login", {
        cnic: cnic.trim(),
        password,
      });
      saveSession(result.session_token, result.applicant.full_name, remember);
      clearCurrentApp();
      router.push("/dashboard");
    } catch (err) {
      setError(err);
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto max-w-md">
      <Card>
        <h1 className="text-xl font-bold tracking-tight text-slate-900">
          Welcome back
        </h1>
        <p className="mt-1 text-sm text-slate-600">
          Log in with the CNIC and password you registered with.
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
              autoComplete="username"
              required
            />
          </Field>

          <Field label="Password">
            <div className="relative">
              <input
                className={`${inputClass} pr-14`}
                type={showPassword ? "text" : "password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
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

          <div className="flex items-center justify-between">
            <label className="flex cursor-pointer items-center gap-2 text-sm text-slate-700">
              <input
                type="checkbox"
                checked={remember}
                onChange={(e) => setRemember(e.target.checked)}
                className="h-4 w-4 rounded border-slate-300 accent-[#0e9f6e]"
              />
              Remember me
            </label>
            <Link
              href="/forgot-password"
              className="text-sm font-semibold text-[#0e9f6e] hover:underline"
            >
              Forgot password?
            </Link>
          </div>

          <ErrorBox error={error} />

          <PrimaryButton type="submit" loading={loading} className="w-full">
            Log in
          </PrimaryButton>
        </form>

        <p className="mt-5 text-center text-sm text-slate-600">
          New here?{" "}
          <Link href="/register" className="font-semibold text-[#0e9f6e] hover:underline">
            Create an account
          </Link>
        </p>
      </Card>
    </div>
  );
}
