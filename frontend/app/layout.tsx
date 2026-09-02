import type { Metadata } from "next";
import "./globals.css";
import Header from "@/components/Header";

export const metadata: Metadata = {
  title: "RoshanScore — AI Credit Assessment",
  description:
    "Alternative-data credit scoring prototype for Pakistan's credit-invisible applicants. Every score ships with its reasons.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-[#f5f7fa] text-slate-900 antialiased">
        <Header />
        <main className="mx-auto w-full max-w-5xl px-4 pb-16 pt-8">
          {children}
        </main>
        <footer className="border-t border-slate-200 bg-white px-4 py-6 text-center text-xs leading-relaxed text-slate-500">
          Prototype trained on synthetic data · Not financial advice · Identity
          verification and data-provider integrations are clearly-labelled
          simulations · Loan decisions remain with the lending institution
        </footer>
      </body>
    </html>
  );
}
