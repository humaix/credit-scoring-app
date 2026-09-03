"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";

import {
  api, setCurrentApp, formatPKR,
  LOAN_HISTORY_OPTIONS, OCCUPATIONS, WALLET_PROVIDERS,
} from "@/lib/api";
import {
  Alert, Card, ErrorBox, Field, PrimaryButton, Stepper, inputClass,
  useRequireSession,
} from "@/components/ui";

interface FormState {
  hasBankAccount: string; // "" | "yes" | "no" — unanswered until chosen
  bankName: string;
  bankAccountTitle: string;
  bankIban: string;
  walletProvider: string;
  age: string;
  occupation: string;
  monthly_income: string;
  monthly_debt_payments: string;
  existing_loan_history: string;
  requested_loan_size: string;
  digital_purchase_frequency: string;
}

const EMPTY: FormState = {
  hasBankAccount: "",
  bankName: "",
  bankAccountTitle: "",
  bankIban: "",
  walletProvider: "",
  age: "",
  occupation: "Salaried",
  monthly_income: "",
  monthly_debt_payments: "",
  existing_loan_history: "No Previous Loan",
  requested_loan_size: "",
  digital_purchase_frequency: "",
};

const IBAN_PATTERN = /^(PK\d{2}[A-Z0-9]{20}|[A-Z0-9]{8,24})$/;

function validate(form: FormState): Record<string, string> {
  const errors: Record<string, string> = {};
  const age = Number(form.age);
  const income = Number(form.monthly_income);
  const debt = Number(form.monthly_debt_payments);
  const loan = Number(form.requested_loan_size);
  const purchases = Number(form.digital_purchase_frequency);

  if (form.hasBankAccount === "yes") {
    if (!form.bankName.trim()) {
      errors.bankName = "Bank name is required.";
    }
    if (!form.bankAccountTitle.trim()) {
      errors.bankAccountTitle = "Account title is required.";
    }
    const iban = form.bankIban.replace(/\s+/g, "").toUpperCase();
    if (!iban) {
      errors.bankIban = "IBAN / account number is required.";
    } else if (!IBAN_PATTERN.test(iban)) {
      errors.bankIban =
        "Enter a Pakistani IBAN (PK…) or an account number of 8–24 letters/digits.";
    }
  }

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

  const hasBank = form.hasBankAccount === "yes";

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
          has_bank_account: hasBank,
          ...(hasBank
            ? {
                bank_name: form.bankName.trim(),
                bank_account_title: form.bankAccountTitle.trim(),
                bank_iban: form.bankIban.replace(/\s+/g, "").toUpperCase(),
              }
            : {}),
          ...(form.walletProvider
            ? { wallet_provider: form.walletProvider }
            : {}),
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
          First: do you have a bank account? Your answer shapes the rest of
          the flow — you can complete the assessment either way.
        </p>

        <form className="mt-6 space-y-4" onSubmit={onSubmit} noValidate>
          {/* ---- Phase 2: the bank-account question comes first ---------- */}
          <div className="rounded-xl border border-slate-200 bg-slate-50/60 p-4">
            <span className="mb-2 block text-sm font-medium text-slate-700">
              Do you have a bank account?
            </span>
            <div className="grid grid-cols-2 gap-3">
              {(["yes", "no"] as const).map((option) => (
                <label
                  key={option}
                  className={`flex cursor-pointer items-center justify-center gap-2 rounded-xl border px-4 py-3 text-sm font-semibold transition ${
                    form.hasBankAccount === option
                      ? "border-[#0e9f6e] bg-emerald-50 text-emerald-900"
                      : "border-slate-300 bg-white text-slate-700 hover:border-slate-400"
                  }`}
                >
                  <input
                    type="radio"
                    name="has_bank_account"
                    value={option}
                    checked={form.hasBankAccount === option}
                    onChange={() => set("hasBankAccount", option)}
                    className="accent-[#0e9f6e]"
                  />
                  {option === "yes" ? "Yes" : "No"}
                </label>
              ))}
            </div>
            {fieldErrors.hasBankAccount ? (
              <p className="mt-2 text-xs font-medium text-red-600">
                {fieldErrors.hasBankAccount}
              </p>
            ) : (
              <p className="mt-2 text-xs text-slate-500">
                {hasBank
                  ? "Add your bank details below — statement verification stays document-based in this prototype."
                  : "No bank account is fine: the assessment runs on alternative data (mobile wallet, telecom, digital activity)."}
              </p>
            )}
          </div>

          {hasBank && (
            <div className="grid gap-4 rounded-xl border border-slate-200 p-4 sm:grid-cols-2">
              <Field label="Bank name" error={fieldErrors.bankName}>
                <input
                  className={inputClass}
                  value={form.bankName}
                  onChange={(e) => set("bankName", e.target.value)}
                  placeholder="e.g. Habib Bank Limited"
                  maxLength={100}
                />
              </Field>
              <Field
                label="Account title"
                hint="The name on the account"
                error={fieldErrors.bankAccountTitle}
              >
                <input
                  className={inputClass}
                  value={form.bankAccountTitle}
                  onChange={(e) => set("bankAccountTitle", e.target.value)}
                  placeholder="e.g. Ali Raza"
                  maxLength={100}
                />
              </Field>
              <Field
                label="IBAN / account number"
                hint="PK IBAN (PK36…) or account number, 8–24 characters"
                error={fieldErrors.bankIban}
              >
                <input
                  className={inputClass}
                  value={form.bankIban}
                  onChange={(e) => set("bankIban", e.target.value)}
                  placeholder="PK36SCBL0000001123456702"
                  autoComplete="off"
                  maxLength={34}
                />
              </Field>
            </div>
          )}

          <Field
            label="Mobile wallet (optional)"
            hint="Which wallet do you use, if any? Used by the wallet activity assessment."
          >
            <select
              className={inputClass}
              value={form.walletProvider}
              onChange={(e) => set("walletProvider", e.target.value)}
            >
              <option value="">I don&apos;t use a mobile wallet</option>
              {WALLET_PROVIDERS.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </Field>

          <div className="border-t border-slate-200 pt-4">
            <h2 className="mb-3 text-sm font-semibold text-slate-700">
              Your profile
            </h2>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Age" hint="18–65" error={fieldErrors.age}>
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
                  onChange={(e) =>
                    set("digital_purchase_frequency", e.target.value)}
                  placeholder="e.g. 6"
                  required
                />
              </Field>
            </div>
          </div>

          <Alert tone="info">
            Declare your profile honestly — this, plus your consented
            alternative data, is what the assessment uses. Income would be
            verified against a financial source in production.
          </Alert>

          <ErrorBox error={error} />

          <PrimaryButton type="submit" loading={loading} className="w-full">
            Submit application
          </PrimaryButton>
        </form>
      </Card>
    </div>
  );
}
