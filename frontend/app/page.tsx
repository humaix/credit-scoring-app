import Link from "next/link";

const HOW_IT_WORKS = [
  {
    step: "1",
    title: "Share your details",
    text: "Register with your CNIC and mobile number, then declare your income, occupation and the loan you need.",
  },
  {
    step: "2",
    title: "Verify your identity",
    text: "A one-time code confirms you own the mobile number (simulated for this prototype — no real SMS is sent).",
  },
  {
    step: "3",
    title: "Choose what you share",
    text: "You explicitly consent to each alternative data category — wallet activity, telecom activity, digital transactions and loan history.",
  },
  {
    step: "4",
    title: "Answer 12 questions",
    text: "A short Financial Behavior Assessment covers discipline, repayment responsibility, spending control and planning.",
  },
  {
    step: "5",
    title: "Get your score — and its reasons",
    text: "An explainable AI model estimates a repayment score (0–100), shows exactly which factors moved it, and produces a PDF report.",
  },
];

const PRINCIPLES = [
  {
    title: "Consent comes first",
    text: "No data source is touched without explicit, category-by-category consent. If you decline, the data is simply never used.",
  },
  {
    title: "Every score is explained",
    text: "You always see which factors raised or lowered the estimate and by how much — no black-box rejections.",
  },
  {
    title: "Honest about what it is",
    text: "Identity verification and provider data are clearly-labelled simulations, the model is trained on synthetic data, and the score is never an approval decision.",
  },
];

export default function Home() {
  return (
    <div className="space-y-14">
      <section className="rise-in rounded-3xl bg-[#0c2f48] px-6 py-14 text-center text-white sm:px-12">
        <span className="inline-flex items-center rounded-full border border-white/25 bg-white/10 px-3.5 py-1 text-xs font-semibold tracking-wide text-emerald-200">
          PROTOTYPE · TRAINED ON SYNTHETIC DATA
        </span>
        <h1 className="mx-auto mt-6 max-w-2xl text-4xl font-bold leading-tight tracking-tight sm:text-5xl">
          Credit assessment for Pakistan&apos;s{" "}
          <span className="text-emerald-300">credit-invisible</span>
        </h1>
        <p className="mx-auto mt-5 max-w-2xl text-base leading-relaxed text-slate-200 sm:text-lg">
          Shopkeepers, freelancers and daily-wage earners use Easypaisa and
          JazzCash every day — yet have no bank account or credit history.
          RoshanScore turns consented alternative data into an explainable
          repayment assessment, with the reasons attached to every score.
        </p>
        <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
          <Link
            href="/register"
            className="inline-flex h-11 items-center justify-center rounded-xl bg-[#0e9f6e] px-6 text-sm font-semibold text-white transition hover:bg-[#0b8a5e]"
          >
            Start an assessment
          </Link>
          <Link
            href="/login"
            className="inline-flex h-11 items-center justify-center rounded-xl border border-white/30 px-6 text-sm font-semibold text-white transition hover:bg-white/10"
          >
            Log in
          </Link>
        </div>
      </section>

      <section>
        <h2 className="text-center text-2xl font-bold tracking-tight text-slate-900">
          How it works
        </h2>
        <ol className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
          {HOW_IT_WORKS.map((item) => (
            <li
              key={item.step}
              className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"
            >
              <span className="flex h-8 w-8 items-center justify-center rounded-full bg-[#0c2f48] text-sm font-bold text-white">
                {item.step}
              </span>
              <h3 className="mt-3 text-sm font-semibold text-slate-900">
                {item.title}
              </h3>
              <p className="mt-1.5 text-xs leading-relaxed text-slate-600">
                {item.text}
              </p>
            </li>
          ))}
        </ol>
      </section>

      <section>
        <h2 className="text-center text-2xl font-bold tracking-tight text-slate-900">
          Built to be trusted
        </h2>
        <div className="mt-8 grid gap-4 md:grid-cols-3">
          {PRINCIPLES.map((item) => (
            <div
              key={item.title}
              className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm"
            >
              <h3 className="text-sm font-semibold text-[#0c2f48]">
                {item.title}
              </h3>
              <p className="mt-2 text-sm leading-relaxed text-slate-600">
                {item.text}
              </p>
            </div>
          ))}
        </div>
      </section>

      <section className="rounded-2xl border border-amber-200 bg-amber-50 px-6 py-5 text-center">
        <p className="mx-auto max-w-3xl text-xs leading-relaxed text-amber-900">
          The score produced by this prototype is a model-estimated repayment
          assessment. It is not a guaranteed probability of repayment and not
          an automatic loan approval or rejection decision. Loan decisions
          remain with the lending institution.
        </p>
      </section>
    </div>
  );
}
