"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";

import {
  api, setCurrentApp, formatPKR,
  LOAN_HISTORY_OPTIONS, OCCUPATIONS,
} from "@/lib/api";
import {
  Card, ErrorBox, Field, PrimaryButton, Stepper, inputClass, useRequireSession,
} from "@/components/ui";

interface FormState {
  age: string;
  occupation: string;
  monthly_income: string;
  monthly_debt_payments: string;
  existing_loan_history: string;
  requested_loan_size: string;
  digital_purchase_frequency: string;
}

const EMPTY: FormState = {
  age: "",
  occupation: "Salaried",
  monthly_income: "",
  monthly_debt_payments: "",
  existing_loan_history: "No Previous Loan",
  requested_loan_size: "",
  digital_purchase_frequency: "",
};

function validate(form: FormState): Record<string, string> {
  const errors: Record<string, string> = {};
  const age = Number(form.age);
  const income = Number(form.monthly_income);
  const debt = Number(form.monthly_debt_payments);
  const loan = Number(form.requested_loan_size);
  const purchases = Number(form.digital_purchase_frequency);

  if (!form.age || !Number.isInteger(age) || age < 18 || age > 65) {
    errors.age = "Age must be a whole number between 18 and 65.";
  }
  if (!form.monthly_income || income < 1000 || income > 5000000) {
    errors.monthly_income = "Monthly income must be between PKR 1,000 and PKR 5,000,000.";
  }
  if (form.monthly_debt_payments === "" || debt < 0 || debt > income) {
    errors.monthly_debt_payments =
      "Monthly debt payments cannot be negative or exceed your monthly income.";
  }
  if (!form.requested_loan_size || loan < 10000 || loan > 10000000) {
    errors.requested_loan_size =
      "Requested loan size must be between PKR 10,000 and PKR 10,000,000.";
  }
  if (
    form.digital_purchase_frequency === ""
    || !Number.isInteger(purchases) || purchases < 0 || purchases > 200
  ) {
    errors.digital_purchase_frequency =
      "Digital purchases per month must be a whole number between 0 and 200.";
  }
  return errors;
}

export default function ApplyPage() {
  const router = useRouter();
  const sessionReady = useRequireSession();
  const [form, setForm] = useState<FormState>(EMPTY);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<unknown>(null);

  if (!sessionReady) return null;

  function set(key: keyof FormState, value: string) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    const errors = validate(form);
    setFieldErrors(errors);
    if (Object.keys(errors).length > 0) return;

    setLoading(true);
    setError(null);
    try {
      const result = await api.post<{ application_id: number; status: string }>(
        "/api/applications",
        {
          age: Number(form.age),
          occupation: form.occupation,
          monthly_income: Number(form.monthly_income),
          monthly_debt_payments: Number(form.monthly_debt_payments),
          existing_loan_history: form.existing_loan_history,
          requested_loan_size: Number(form.requested_loan_size),
          digital_purchase_frequency: Number(form.digital_purchase_frequency),
        },
      );
      setCurrentApp(result.application_id);
      router.push("/verify");
    } catch (err) {
      setError(err);
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto max-w-2xl">
      <Stepper current={0} />
      <Card>
        <h1 className="text-xl font-bold tracking-tight text-slate-900">
          Loan application
        </h1>
        <p className="mt-1 text-sm text-slate-600">
          Declare your profile — this, plus your consented alternative data,
          is what the assessment uses. Income would be verified against a
          financial source in production.
        </p>

        <form className="mt-6 space-y-4" onSubmit={onSubmit} noValidate>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field
              label="Age"
              hint="18–65"
              error={fieldErrors.age}
            >
              <input
                className={inputClass}
                type="number"
                value={form.age}
                onChange={(e) => set("age", e.target.value)}
                placeholder="e.g. 35"
                required
              />
            </Field>

            <Field label="Occupation">
              <select
                className={inputClass}
                value={form.occupation}
                onChange={(e) => set("occupation", e.target.value)}
              >
                {OCCUPATIONS.map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </select>
            </Field>

            <Field
              label="Monthly income (PKR)"
              hint={`Allowed: ${formatPKR(1000)} – ${formatPKR(5000000)}`}
              error={fieldErrors.monthly_income}
            >
              <input
                className={inputClass}
                type="number"
                value={form.monthly_income}
                onChange={(e) => set("monthly_income", e.target.value)}
                placeholder="e.g. 65000"
                required
              />
            </Field>

            <Field
              label="Monthly debt payments (PKR)"
              hint="Total instalments you currently pay each month"
              error={fieldErrors.monthly_debt_payments}
            >
              <input
                className={inputClass}
                type="number"
                value={form.monthly_debt_payments}
                onChange={(e) => set("monthly_debt_payments", e.target.value)}
                placeholder="e.g. 12000"
                required
              />
            </Field>

            <Field label="Existing loan history">
              <select
                className={inputClass}
                value={form.existing_loan_history}
                onChange={(e) => set("existing_loan_history", e.target.value)}
              >
                {LOAN_HISTORY_OPTIONS.map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </select>
            </Field>

            <Field
              label="Requested loan size (PKR)"
              hint={`Allowed: ${formatPKR(10000)} – ${formatPKR(10000000)}`}
              error={fieldErrors.requested_loan_size}
            >
              <input
                className={inputClass}
                type="number"
                value={form.requested_loan_size}
                onChange={(e) => set("requested_loan_size", e.target.value)}
                placeholder="e.g. 200000"
                required
              />
            </Field>

            <Field
              label="Digital purchases per month"
              hint="Online / wallet purchases (0–200)"
              error={fieldErrors.digital_purchase_frequency}
            >
              <input
                className={inputClass}
                type="number"
                value={form.digital_purchase_frequency}
                onChange={(e) => set("digital_purchase_frequency", e.target.value)}
                placeholder="e.g. 6"
                required
              />
            </Field>
          </div>

          <ErrorBox error={error} />

          <PrimaryButton type="submit" loading={loading} className="w-full">
            Submit application
          </PrimaryButton>
        </form>
      </Card>
    </div>
  );
}
