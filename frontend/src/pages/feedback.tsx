import React, { useEffect, useState } from "react";
import type { NextPage } from "next";
import Layout from "@/components/Layout";
import PageHeader from "@/components/PageHeader";
import ErrorAlert from "@/components/ErrorAlert";
import { api, type FeedbackRequest } from "@/lib/api";

type Rating = "helpful" | "not_helpful" | "verify_commit" | "";

type StoredSolution = {
  solution_id?: string;
  solutionId?: string;
  id?: string;
  solution_title?: string;
  title?: string;
  confidence?: string;
  match_score?: number;
  matchScore?: number;
  evidence?: Array<{
    source?: string;
    source_type?: string;
    ticket_id?: string;
    document_id?: string;
  }>;
};

const Page: NextPage = () => {
  const [solutionId, setSolutionId] = useState("");
  const [rating, setRating] = useState<Rating>("");
  const [notes, setNotes] = useState("");
  const [loading, setLoading] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedSolution, setSavedSolution] =
    useState<StoredSolution | null>(null);

  useEffect(() => {
    try {
      const raw = window.localStorage.getItem("solvia:last-solution");

      if (!raw) return;

      const parsed = JSON.parse(raw) as StoredSolution;
      setSavedSolution(parsed);

      const detectedId =
        parsed.solution_id || parsed.solutionId || parsed.id || "";

      if (detectedId) {
        setSolutionId(detectedId);
      }
    } catch (restoreError) {
      console.warn("Unable to restore saved solution", restoreError);
    }
  }, []);

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    if (!solutionId.trim() || !rating) return;

    setLoading(true);
    setError(null);

    const payload: FeedbackRequest = {
      solution_id: solutionId.trim(),
      rating,
      notes: notes.trim() || null,
    };

    try {
      await api.postFeedback(payload);
      setSubmitted(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  const solutionTitle =
    savedSolution?.solution_title ||
    savedSolution?.title ||
    "SOLVIA recommendation";

  const matchScore =
    savedSolution?.match_score ?? savedSolution?.matchScore ?? null;

  const confidence = savedSolution?.confidence || "Not available";

  const evidence = savedSolution?.evidence?.[0];

  const source =
    evidence?.source ||
    evidence?.source_type ||
    "Enterprise knowledge";

  const reference =
    evidence?.ticket_id ||
    evidence?.document_id ||
    "Evidence-backed recommendation";

  return (
    <Layout fullWidth>
      <PageHeader
        title="Feedback"
        subtitle="Help SOLVIA understand whether this recommendation was useful, accurate, and safe to apply."
      />

      <div className="w-full max-w-none">
        {submitted ? (
          <SubmittedState />
        ) : (
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
            {/* Top-left: Recommendation Under Review */}
            {savedSolution ? (
              <section className="h-full rounded-2xl border border-indigo-400/30 bg-gradient-to-br from-[#111a2d] via-[#0d1628] to-[#08111f] p-6 shadow-[0_0_40px_rgba(79,70,229,0.08)]">
                <div className="flex flex-wrap items-start justify-between gap-5">
                  <div>
                    <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-indigo-300">
                      Recommendation under review
                    </p>

                    <h2 className="mt-2 max-w-2xl text-2xl font-semibold leading-tight text-white">
                      {solutionTitle}
                    </h2>
                  </div>

                  {matchScore !== null && (
                    <div className="rounded-xl border border-indigo-400/20 bg-indigo-500/10 px-4 py-3 text-center">
                      <div className="text-2xl font-semibold text-indigo-200">
                        {matchScore}%
                      </div>

                      <div className="text-[10px] uppercase tracking-wider text-slate-500">
                        Match score
                      </div>
                    </div>
                  )}
                </div>

                <div className="mt-5 flex flex-wrap gap-2">
                  <span className="rounded-full border border-indigo-400/30 bg-indigo-500/10 px-3 py-1.5 text-xs font-semibold uppercase tracking-wider text-indigo-200">
                    Confidence: {confidence}
                  </span>

                  <span className="rounded-full border border-cyan-400/20 bg-cyan-400/5 px-3 py-1.5 text-xs text-cyan-200">
                    {source} · {reference}
                  </span>
                </div>

                <div className="mt-5 rounded-xl border border-white/[0.08] bg-[#030817]/60 p-4">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                    Solution ID
                  </p>

                  <p className="mt-2 break-all font-mono text-xs text-slate-300">
                    {solutionId || "Not detected automatically"}
                  </p>
                </div>
              </section>
            ) : (
              <section className="h-full rounded-2xl border border-amber-400/25 bg-amber-400/[0.06] p-5">
                <p className="text-sm font-semibold text-amber-200">
                  No recent solution detected
                </p>

                <p className="mt-1 text-sm leading-6 text-slate-400">
                  Generate a recommendation in Solution Finder first, or enter
                  a Solution ID manually below.
                </p>
              </section>
            )}

            {/* Top-right: Human Validation */}
            <RelatedSection />

            {/* Bottom: Full-width Feedback Form */}
            <form
              onSubmit={handleSubmit}
              className="lg:col-span-2 rounded-2xl border border-white/[0.1] bg-gradient-to-br from-[#111a2d] to-[#0b1424] p-6 shadow-[0_0_35px_rgba(15,23,42,0.35)] sm:p-7"
            >
              <div className="mb-6">
                <div className="mb-2 flex items-center justify-between gap-3">
                  <label
                    htmlFor="solutionId"
                    className="text-sm font-semibold text-slate-100"
                  >
                    Solution ID
                  </label>

                  <span className="text-[11px] uppercase tracking-wider text-slate-500">
                    Fallback input
                  </span>
                </div>

                <input
                  id="solutionId"
                  type="text"
                  value={solutionId}
                  onChange={(event) => setSolutionId(event.target.value)}
                  placeholder="Paste a Solution ID if needed"
                  className="w-full rounded-xl border border-white/10 bg-[#030817] px-4 py-3 text-sm text-white placeholder-slate-600 outline-none transition focus:border-indigo-400 focus:ring-4 focus:ring-indigo-500/10"
                />

                <p className="mt-2 text-xs leading-5 text-slate-500">
                  Automatically loaded from your latest SOLVIA recommendation
                  when available.
                </p>
              </div>

              <div className="mb-6">
                <label className="mb-3 block text-sm font-semibold text-slate-100">
                  How did this recommendation perform?
                  <span className="ml-1 text-rose-400">*</span>
                </label>

                <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
                  <RatingButton
                    selected={rating === "helpful"}
                    label="Helpful"
                    description="The recommendation addressed the issue."
                    color="emerald"
                    onClick={() => setRating("helpful")}
                  />

                  <RatingButton
                    selected={rating === "not_helpful"}
                    label="Not Helpful"
                    description="The recommendation was wrong or incomplete."
                    color="rose"
                    onClick={() => setRating("not_helpful")}
                  />

                  <RatingButton
                    selected={rating === "verify_commit"}
                    label="Verify & Commit"
                    description="The evidence was reviewed and applied."
                    color="amber"
                    onClick={() => setRating("verify_commit")}
                  />
                </div>
              </div>

              <div className="mb-6">
                <label
                  htmlFor="notes"
                  className="mb-2 block text-sm font-semibold text-slate-100"
                >
                  Notes{" "}
                  <span className="font-normal text-slate-500">
                    (optional)
                  </span>
                </label>

                <textarea
                  id="notes"
                  rows={4}
                  value={notes}
                  onChange={(event) => setNotes(event.target.value)}
                  placeholder="Add context, what you tried, or what was missing..."
                  className="w-full resize-y rounded-xl border border-white/10 bg-[#030817] px-4 py-3 text-sm leading-6 text-white placeholder-slate-600 outline-none transition focus:border-indigo-400 focus:ring-4 focus:ring-indigo-500/10"
                />
              </div>

              {error && (
                <div className="mb-5">
                  <ErrorAlert
                    message={error}
                    onRetry={() => setError(null)}
                  />
                </div>
              )}

              <div className="flex flex-col-reverse gap-4 border-t border-white/[0.08] pt-5 sm:flex-row sm:items-center sm:justify-between">
                <p className="text-xs leading-5 text-slate-500">
                  Feedback is recorded for audit and analytics only. It does
                  not execute SAP operations.
                </p>

                <button
                  type="submit"
                  disabled={loading || !solutionId.trim() || !rating}
                  className="inline-flex items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-violet-600 via-indigo-500 to-cyan-400 px-5 py-3 text-sm font-semibold text-white shadow-lg shadow-indigo-950/40 transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  {loading ? "Recording feedback..." : "Submit Feedback"}
                </button>
              </div>
            </form>
          </div>
        )}
      </div>
    </Layout>
  );
};

function RatingButton({
  selected,
  label,
  description,
  color,
  onClick,
}: {
  selected: boolean;
  label: string;
  description: string;
  color: "emerald" | "rose" | "amber";
  onClick: () => void;
}) {
  const selectedStyles = {
    emerald:
      "border-emerald-400/50 bg-emerald-400/10 text-emerald-200",
    rose: "border-rose-400/50 bg-rose-400/10 text-rose-200",
    amber:
      "border-amber-400/50 bg-amber-400/10 text-amber-200",
  };

  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-xl border p-4 text-left transition ${
        selected
          ? selectedStyles[color]
          : "border-white/[0.1] bg-[#030817]/70 text-slate-300 hover:border-indigo-400/40 hover:bg-indigo-500/[0.06]"
      }`}
    >
      <div className="flex items-center justify-between gap-3">
        <span className="text-sm font-semibold">{label}</span>

        {selected && <span className="text-xs">Selected</span>}
      </div>

      <p className="mt-2 text-xs leading-5 text-slate-500">
        {description}
      </p>
    </button>
  );
}

function SubmittedState() {
  return (
    <div className="rounded-2xl border border-emerald-400/30 bg-emerald-400/[0.06] p-10 text-center">
      <div className="mx-auto mb-5 flex h-16 w-16 items-center justify-center rounded-full bg-emerald-400/15 text-emerald-300">
        ✓
      </div>

      <h3 className="text-xl font-semibold text-white">
        Feedback recorded
      </h3>

      <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-slate-400">
        Your rating has been saved. The audit trail and impact analytics will
        reflect this validation.
      </p>
    </div>
  );
}

function RelatedSection() {
  return (
    <section className="h-full rounded-2xl border border-white/[0.1] bg-gradient-to-br from-[#101a2d] to-[#09111f] p-6">
      <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-indigo-300">
        Human validation loop
      </p>

      <h3 className="mt-2 text-lg font-semibold text-white">
        How feedback works
      </h3>

      <ul className="mt-5 space-y-4 text-sm leading-6 text-slate-400">
        <li>
          <strong className="text-emerald-300">Helpful</strong> — the solution
          addressed the issue.
        </li>

        <li>
          <strong className="text-rose-300">Not Helpful</strong> — the
          recommendation was incorrect or incomplete.
        </li>

        <li>
          <strong className="text-amber-300">Verify & Commit</strong> — you
          reviewed the evidence and applied the recommendation.
        </li>
      </ul>

      <div className="mt-5 border-t border-white/[0.08] pt-4 text-xs leading-5 text-slate-500">
        Verify & Commit records human validation only. It does not execute SAP
        operations.
      </div>
    </section>
  );
}

export default Page;