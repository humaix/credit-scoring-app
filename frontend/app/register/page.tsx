"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import {
  api, clearCurrentApp, saveSession, type RegisterResponse,
} from "@/lib/api";
import { Card, ErrorBox, Field, PrimaryButton, inputClass } from "@/components/ui";

export default function RegisterPage() {
  const router = useRouter();
  const [fullName, setFullName] = useState("");
  const [cnic, setCnic] = useState("");
  const [mobile, setMobile] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<unknown>(null);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const result = await api.post<RegisterResponse>("/api/auth/register", {
        full_name: fullName.trim(),
        cnic: cnic.trim(),
        mobile: mobile.trim(),
      });
      saveSession(result.session_token, result.applicant.full_name);
      clearCurrentApp();
      router.push("/apply");
    } catch (err) {
      setError(err);
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto max-w-md">
      <Card>
        <h1 className="text-xl font-bold tracking-tight text-slate-900">
          Create your account
        </h1>
        <p className="mt-1 text-sm text-slate-600">
          No passwords in this prototype — your CNIC and mobile number are
          your credentials.
        </p>

        <form className="mt-6 space-y-4" onSubmit={onSubmit}>
          <Field label="Full name">
            <input
              className={inputClass}
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              placeholder="e.g. Ali Raza"
              required
              minLength={2}
              maxLength={100}
            />
          </Field>

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
            Create account
          </PrimaryButton>
        </form>

        <p className="mt-5 text-center text-sm text-slate-600">
          Already registered?{" "}
          <Link href="/login" className="font-semibold text-[#0e9f6e] hover:underline">
            Log in
          </Link>
        </p>
      </Card>
    </div>
  );
}
