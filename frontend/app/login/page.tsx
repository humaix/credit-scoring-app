"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { api, clearCurrentApp, saveSession, type LoginResponse } from "@/lib/api";
import { Card, ErrorBox, Field, PrimaryButton, inputClass } from "@/components/ui";

export default function LoginPage() {
  const router = useRouter();
  const [cnic, setCnic] = useState("");
  const [mobile, setMobile] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<unknown>(null);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const result = await api.post<LoginResponse>("/api/auth/login", {
        cnic: cnic.trim(),
        mobile: mobile.trim(),
      });
      saveSession(result.session_token, result.applicant.full_name);
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
          Log in with the CNIC and mobile number you registered with.
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

          <Field
            label="Mobile number"
            hint="11 digits starting with 03, e.g. 03001234567"
          >
            <input
              className={inputClass}
              value={mobile}
              onChange={(e) => setMobile(e.target.value)}
              placeholder="03001234567"
              inputMode="numeric"
              autoComplete="off"
              required
            />
          </Field>

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
