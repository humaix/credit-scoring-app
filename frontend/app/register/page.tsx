"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import {
  api, clearCurrentApp, saveSession, type RegisterResponse,
} from "@/lib/api";
import CameraCapture from "@/components/CameraCapture";
import {
  Alert, Card, ErrorBox, Field, PrimaryButton, inputClass,
} from "@/components/ui";

const PASSWORD_HINT =
  "At least 8 characters, including at least one letter and one digit.";

export default function RegisterPage() {
  const router = useRouter();
  const [fullName, setFullName] = useState("");
  const [cnic, setCnic] = useState("");
  const [email, setEmail] = useState("");
  const [mobile, setMobile] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [frontImage, setFrontImage] = useState<string | null>(null);
  const [backImage, setBackImage] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [formError, setFormError] = useState<string | null>(null);

  function validate(): string | null {
    if (
      password.length < 8 ||
      !/[A-Za-z]/.test(password) ||
      !/\d/.test(password)
    ) {
      return `Password is too weak — ${PASSWORD_HINT.toLowerCase()}`;
    }
    if (password !== confirmPassword) {
      return "Passwords do not match.";
    }
    if (!frontImage || !backImage) {
      return "Please capture both the front and back of your CNIC.";
    }
    return null;
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    const problem = validate();
    if (problem) {
      setFormError(problem);
      return;
    }
    setFormError(null);
    setLoading(true);
    setError(null);
    try {
      const result = await api.post<RegisterResponse>("/api/auth/register", {
        full_name: fullName.trim(),
        cnic: cnic.trim(),
        email: email.trim(),
        mobile: mobile.trim(),
        password,
        confirm_password: confirmPassword,
        cnic_front_image: frontImage,
        cnic_back_image: backImage,
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
          Register with a password you choose, then capture your CNIC with the
          camera. Images are quality-checked only — this prototype is not
          connected to NADRA and performs no OCR.
        </p>

        <form className="mt-6 space-y-4" onSubmit={onSubmit}>
          <Field label="Full name">
            <input
              className={inputClass}
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              placeholder="e.g. Ali Raza"
              autoComplete="name"
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
            label="Email address"
            hint="Used only for password recovery and account notices"
          >
            <input
              className={inputClass}
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              autoComplete="email"
              required
              maxLength={120}
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
              autoComplete="tel"
              required
            />
          </Field>

          <Field label="Password" hint={PASSWORD_HINT}>
            <input
              className={inputClass}
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="new-password"
              minLength={8}
              maxLength={128}
              required
            />
          </Field>

          <Field label="Confirm password">
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

          <div className="space-y-3 pt-2">
            <CameraCapture
              label="CNIC front"
              hint="Place the front of your card in the frame"
              value={frontImage}
              onChange={setFrontImage}
            />
            <CameraCapture
              label="CNIC back"
              hint="Flip the card over to capture the back"
              value={backImage}
              onChange={setBackImage}
            />
          </div>

          <ErrorBox error={error} />
          {formError && !error && (
            <Alert tone="error">
              <p className="font-medium">{formError}</p>
            </Alert>
          )}

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
