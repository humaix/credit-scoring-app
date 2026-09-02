"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { clearSession, sessionToken } from "@/lib/api";

export default function Header() {
  const router = useRouter();
  const pathname = usePathname();
  const [loggedIn, setLoggedIn] = useState(false);

  useEffect(() => {
    // re-check on every route change AND whenever the session helpers
    // announce a change, so the nav never goes stale during the flow
    const sync = () => setLoggedIn(Boolean(sessionToken()));
    sync();
    window.addEventListener("ccs-session", sync);
    return () => window.removeEventListener("ccs-session", sync);
  }, [pathname]);

  return (
    <header className="sticky top-0 z-20 border-b border-slate-200 bg-white/90 backdrop-blur">
      <div className="mx-auto flex w-full max-w-5xl items-center justify-between px-4 py-3.5">
        <Link href="/" className="flex items-center gap-2.5">
          <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-[#0c2f48]">
            <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden>
              <path
                d="M3 14V10M7.5 14V6M12 14V8M16.5 14V3.5"
                stroke="#34d399"
                strokeWidth="2.2"
                strokeLinecap="round"
              />
            </svg>
          </span>
          <span className="text-lg font-bold tracking-tight text-[#0c2f48]">
            Roshan<span className="text-[#0e9f6e]">Score</span>
          </span>
        </Link>
        <nav className="flex items-center gap-1.5 text-sm font-medium">
          {loggedIn ? (
            <>
              <Link
                href="/dashboard"
                className="rounded-lg px-3 py-2 text-slate-600 transition hover:bg-slate-100 hover:text-slate-900"
              >
                Dashboard
              </Link>
              <button
                onClick={() => {
                  clearSession();
                  router.push("/");
                }}
                className="rounded-lg px-3 py-2 text-slate-600 transition hover:bg-slate-100 hover:text-slate-900"
              >
                Log out
              </button>
            </>
          ) : (
            <Link
              href="/login"
              className="rounded-lg px-3 py-2 text-slate-600 transition hover:bg-slate-100 hover:text-slate-900"
            >
              Log in
            </Link>
          )}
        </nav>
      </div>
    </header>
  );
}
