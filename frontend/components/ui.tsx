"use client";

// Shared UI primitives — one place for the product's look and feel.

import { useEffect, useState, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import {
  ApiError, api, currentAppId, nextStepFor, sessionToken,
  type ApplicationDetail,
} from "@/lib/api";

export function Card({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={`rounded-2xl border border-slate-200 bg-white p-6 shadow-sm ${className}`}
    >
      {children}
    </div>
  );
}

export function PrimaryButton({
  children,
  loading = false,
  className = "",
  ...rest
}: {
  children: ReactNode;
  loading?: boolean;
} & React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      {...rest}
      disabled={rest.disabled || loading}
      className={`inline-flex items-center justify-center gap-2 rounded-xl bg-[#0c2f48] px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-[#14537d] focus:outline-none focus:ring-2 focus:ring-[#14537d] focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 ${className}`}
    >
      {loading && <Spinner />}
      {children}
    </button>
  );
}

export function SecondaryButton({
  children,
  className = "",
  ...rest
}: {
  children: ReactNode;
} & React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      {...rest}
      className={`inline-flex items-center justify-center gap-2 rounded-xl border border-slate-300 bg-white px-5 py-2.5 text-sm font-semibold text-slate-700 transition hover:border-slate-400 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50 ${className}`}
    >
      {children}
    </button>
  );
}

export function Spinner({ className = "" }: { className?: string }) {
  return (
    <span
      className={`inline-block h-4 w-4 animate-spin rounded-full border-2 border-white/40 border-t-white ${className}`}
      aria-hidden
    />
  );
}

export function PageSpinner() {
  return (
    <div className="flex justify-center py-24">
      <span className="inline-block h-8 w-8 animate-spin rounded-full border-[3px] border-slate-200 border-t-[#0c2f48]" />
    </div>
  );
}

export function Field({
  label,
  hint,
  error,
  children,
}: {
  label: string;
  hint?: string;
  error?: string;
  children: ReactNode;
}) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-sm font-medium text-slate-700">
        {label}
      </span>
      {children}
      {hint && !error && (
        <span className="mt-1 block text-xs text-slate-500">{hint}</span>
      )}
      {error && (
        <span className="mt-1 block text-xs font-medium text-red-600">
          {error}
        </span>
      )}
    </label>
  );
}

export const inputClass =
  "w-full rounded-xl border border-slate-300 bg-white px-3.5 py-2.5 text-sm text-slate-900 placeholder-slate-400 shadow-sm transition focus:border-[#14537d] focus:outline-none focus:ring-2 focus:ring-[#14537d]/25 disabled:bg-slate-50";

export function Alert({
  tone = "info",
  children,
}: {
  tone?: "info" | "success" | "warning" | "error";
  children: ReactNode;
}) {
  const tones: Record<string, string> = {
    info: "border-sky-200 bg-sky-50 text-sky-900",
    success: "border-emerald-200 bg-emerald-50 text-emerald-900",
    warning: "border-amber-200 bg-amber-50 text-amber-900",
    error: "border-red-200 bg-red-50 text-red-900",
  };
  return (
    <div className={`rounded-xl border px-4 py-3 text-sm ${tones[tone]}`}>
      {children}
    </div>
  );
}

export function ErrorBox({ error }: { error: unknown }) {
  if (!error) return null;
  const message =
    error instanceof ApiError ? error.message : "Something went wrong. Please try again.";
  return (
    <Alert tone="error">
      <p className="font-medium">{message}</p>
      {error instanceof ApiError && error.details.length > 0 && (
        <ul className="mt-1.5 list-inside list-disc space-y-0.5 text-xs">
          {error.details.map((d, i) => (
            <li key={i}>
              {d.field === "__all__" ? "" : `${d.field}: `}
              {d.issue}
            </li>
          ))}
        </ul>
      )}
    </Alert>
  );
}

const STATUS_STYLES: Record<string, string> = {
  created: "bg-slate-100 text-slate-700",
  verified: "bg-sky-100 text-sky-800",
  consented: "bg-indigo-100 text-indigo-800",
  assessed: "bg-amber-100 text-amber-800",
  scored: "bg-emerald-100 text-emerald-800",
};

const STATUS_LABELS: Record<string, string> = {
  created: "Application submitted",
  verified: "Identity verified",
  consented: "Consent granted",
  assessed: "Assessment complete",
  scored: "Scored",
};

export function StatusBadge({ status }: { status: string }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold ${
        STATUS_STYLES[status] ?? "bg-slate-100 text-slate-700"
      }`}
    >
      {STATUS_LABELS[status] ?? status}
    </span>
  );
}

const STEPS = ["Application", "Identity", "Consent", "Assessment", "Result"];

export function Stepper({ current }: { current: number }) {
  return (
    <ol className="mb-8 flex items-center" aria-label="Progress">
      {STEPS.map((label, index) => {
        const state =
          index < current ? "done" : index === current ? "active" : "todo";
        return (
          <li key={label} className="flex items-center">
            <div className="flex items-center gap-2">
              <span
                className={`flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold ${
                  state === "done"
                    ? "bg-[#0e9f6e] text-white"
                    : state === "active"
                      ? "bg-[#0c2f48] text-white"
                      : "bg-slate-200 text-slate-500"
                }`}
              >
                {state === "done" ? "✓" : index + 1}
              </span>
              <span
                className={`hidden text-xs font-medium sm:block ${
                  state === "todo" ? "text-slate-400" : "text-slate-700"
                }`}
              >
                {label}
              </span>
            </div>
            {index < STEPS.length - 1 && (
              <span
                className={`mx-2 h-0.5 w-6 sm:w-10 ${
                  index < current ? "bg-[#0e9f6e]" : "bg-slate-200"
                }`}
              />
            )}
          </li>
        );
      })}
    </ol>
  );
}

/** Redirects to /login unless a session token exists. */
export function useRequireSession(): boolean {
  const router = useRouter();
  const [ready, setReady] = useState(false);
  useEffect(() => {
    if (!sessionToken()) {
      router.replace("/login");
      return;
    }
    setReady(true);
  }, [router]);
  return ready;
}

/**
 * Loads the in-progress application (ccs_app) for a flow step.
 * Redirects to /login without a session, /dashboard without an application,
 * and to the application's actual next step when the status doesn't match
 * `expectedStatus` — so no step can be done out of order or twice.
 */
export function useCurrentApplication(expectedStatus?: string) {
  const router = useRouter();
  const [app, setApp] = useState<ApplicationDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    const token = sessionToken();
    const id = currentAppId();
    if (!token) {
      router.replace("/login");
      return;
    }
    if (!id) {
      router.replace("/dashboard");
      return;
    }
    let cancelled = false;
    api
      .get<ApplicationDetail>(`/api/applications/${id}`)
      .then((detail) => {
        if (cancelled) return;
        if (expectedStatus && detail.status !== expectedStatus) {
          router.replace(nextStepFor(detail.status));
          return;
        }
        setApp(detail);
        setLoading(false);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err);
        setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [router, expectedStatus]);

  return { app, loading, error };
}
