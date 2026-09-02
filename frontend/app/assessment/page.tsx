"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { api, type QuestionnaireSubmitResult, type QuestionsResponse } from "@/lib/api";
import {
  Alert, Card, ErrorBox, PageSpinner, PrimaryButton, Stepper,
  useCurrentApplication,
} from "@/components/ui";

export default function AssessmentPage() {
  const router = useRouter();
  const { app, loading, error } = useCurrentApplication("consented");

  const [questions, setQuestions] = useState<QuestionsResponse | null>(null);
  const [loadError, setLoadError] = useState<unknown>(null);
  // answers[questionIndex] = 1..5, 0 = unanswered
  const [answers, setAnswers] = useState<number[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<unknown>(null);
  const [result, setResult] = useState<QuestionnaireSubmitResult | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .get<QuestionsResponse>("/api/assessment/questions")
      .then((data) => {
        if (cancelled) return;
        setQuestions(data);
        setAnswers(new Array(data.questions.length).fill(0));
      })
      .catch((err) => {
        if (!cancelled) setLoadError(err);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (loading) return <PageSpinner />;
  if (error) {
    return (
      <div className="mx-auto max-w-md">
        <ErrorBox error={error} />
      </div>
    );
  }
  if (!app) return null;

  const answeredAll =
    questions !== null && answers.length === questions.questions.length
    && answers.every((value) => value >= 1);

  function choose(index: number, value: number) {
    setAnswers((prev) => {
      const next = [...prev];
      next[index] = value;
      return next;
    });
  }

  async function submit() {
    setSubmitting(true);
    setSubmitError(null);
    try {
      const outcome = await api.post<QuestionnaireSubmitResult>(
        "/api/assessment/psychometric",
        { application_id: app!.id, answers },
      );
      setResult(outcome);
    } catch (err) {
      setSubmitError(err);
    } finally {
      setSubmitting(false);
    }
  }

  if (result) {
    return (
      <div className="mx-auto max-w-xl">
        <Stepper current={3} />
        <Card>
          <h1 className="text-xl font-bold tracking-tight text-slate-900">
            Assessment completed
          </h1>
          <p className="mt-1 text-sm text-slate-600">
            Your financial behaviour answers have been scored.
          </p>

          <div className="rise-in mt-6 rounded-2xl border border-slate-200 bg-slate-50 p-6 text-center">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Assessment score
            </p>
            <p className="mt-2 text-4xl font-bold text-[#0c2f48]">
              {result.psychometric_score.toFixed(1)}
              <span className="text-lg font-medium text-slate-400"> / 100</span>
            </p>
          </div>

          {result.consistency_warnings.length > 0 && (
            <div className="mt-4">
              <Alert tone="warning">
                <p className="font-semibold">Consistency notes</p>
                <ul className="mt-1.5 list-inside list-disc space-y-0.5 text-xs">
                  {result.consistency_warnings.map((warning) => (
                    <li key={warning}>{warning}</li>
                  ))}
                </ul>
                <p className="mt-1.5 text-xs">
                  These are assessment-quality indicators only — they never
                  change your score.
                </p>
              </Alert>
            </div>
          )}

          <div className="mt-4">
            <Alert tone="info">{result.note}</Alert>
          </div>

          <PrimaryButton
            className="mt-6 w-full"
            onClick={() => router.push("/processing")}
          >
            Continue to assessment
          </PrimaryButton>
        </Card>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl">
      <Stepper current={3} />
      <Card>
        <h1 className="text-xl font-bold tracking-tight text-slate-900">
          Financial Behavior Assessment
        </h1>
        <p className="mt-1 text-sm text-slate-600">
          12 statements about how you manage money. Answer honestly — there
          are no right or wrong answers, and some statements are deliberately
          worded in opposite directions.
        </p>

        {loadError ? (
          <div className="mt-4"><ErrorBox error={loadError} /></div>
        ) : null}

        {questions && (
          <>
            <div className="mt-6 space-y-6">
              {questions.questions.map((question, index) => (
                <fieldset key={question.id} className="rise-in">
                  <legend className="text-sm font-medium text-slate-900">
                    <span className="mr-2 text-xs font-semibold text-slate-400">
                      Q{index + 1}
                    </span>
                    {question.text}
                  </legend>
                  <p className="mt-0.5 text-[11px] font-medium uppercase tracking-wide text-slate-400">
                    {question.dimension}
                  </p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {questions.scale.map((label, option) => (
                      <label
                        key={label}
                        className={`cursor-pointer rounded-lg border px-3 py-1.5 text-xs font-medium transition ${
                          answers[index] === option + 1
                            ? "border-[#0c2f48] bg-[#0c2f48] text-white"
                            : "border-slate-200 bg-white text-slate-600 hover:border-slate-300"
                        }`}
                      >
                        <input
                          type="radio"
                          className="sr-only"
                          name={`q-${question.id}`}
                          checked={answers[index] === option + 1}
                          onChange={() => choose(index, option + 1)}
                        />
                        {label}
                      </label>
                    ))}
                  </div>
                </fieldset>
              ))}
            </div>

            <div className="mt-4">
              <Alert tone="info">{questions.note}</Alert>
            </div>

            <div className="mt-4">
              <ErrorBox error={submitError} />
            </div>

            <PrimaryButton
              className="mt-2 w-full"
              loading={submitting}
              disabled={!answeredAll}
              onClick={submit}
            >
              {answeredAll
                ? "Submit assessment"
                : `Answer all ${questions.questions.length} questions to continue`}
            </PrimaryButton>
          </>
        )}
      </Card>
    </div>
  );
}
