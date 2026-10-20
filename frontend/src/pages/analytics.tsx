import React, { useEffect } from "react";
import type { NextPage } from "next";
import Layout from "@/components/Layout";
import LoadingState from "@/components/LoadingState";
import ErrorAlert from "@/components/ErrorAlert";
import {
  api,
  errorMessage,
  type AnalyticsSolutionUsage,
  type AnalyticsFeedbackScores,
} from "@/lib/api";

const Page: NextPage = () => {
  const [usage, setUsage] = React.useState<AnalyticsSolutionUsage | null>(null);
  const [scores, setScores] = React.useState<AnalyticsFeedbackScores | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);

    try {
      const [usageResult, scoresResult] = await Promise.all([
        api.getSolutionUsage(),
        api.getFeedbackScores(),
      ]);

      setUsage(usageResult);
      setScores(scoresResult);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const feedbackTotal = scores?.total ?? 0;

  return (
    <Layout>
      <section className="mb-8">
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-3xl font-semibold tracking-tight text-white">
            Impact Analytics
          </h1>

          <span className="rounded-full border border-cyan-400/25 bg-cyan-400/10 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-cyan-300">
            Operational signal
          </span>
        </div>

        <p className="mt-3 max-w-3xl text-sm leading-7 text-slate-400">
          Monitor SOLVIA usage, recommendation confidence, human feedback, and knowledge gaps across enterprise systems.
        </p>
      </section>

      {loading && <LoadingState message="Loading impact analytics..." />}
      {error && <ErrorAlert message={error} onRetry={load} />}

      {!loading && !error && usage && scores && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-5">
            <AnalyticsMetric
              label="Total solutions"
              value={usage.total_solutions}
              sub="generated"
              accent="indigo"
            />

            <AnalyticsMetric
              label="Helpful"
              value={scores.helpful}
              sub={percentage(scores.helpful, feedbackTotal)}
              accent="emerald"
            />

            <AnalyticsMetric
              label="Verify & commit"
              value={scores.verify_commit}
              sub="human-validated"
              accent="amber"
            />

            <AnalyticsMetric
              label="Not helpful"
              value={scores.not_helpful}
              sub={percentage(scores.not_helpful, feedbackTotal)}
              accent="rose"
            />

            <AnalyticsMetric
              label="Knowledge Gaps"
              value={`${usage.gap_frequency_rate ?? 0}%`}
              sub={`${usage.gap_count ?? 0} queries flagged`}
              accent="amber"
            />
          </div>

          <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
            <BreakdownCard
              title="Solutions by confidence"
              eyebrow="Recommendation quality"
              breakdown={usage.by_confidence}
              type="confidence"
              emptyMessage="No generated solution data yet."
            />

            <BreakdownCard
              title="Feedback by rating"
              eyebrow="Human validation"
              breakdown={usage.by_feedback}
              type="feedback"
              emptyMessage="No feedback has been recorded yet."
            />
          </div>

          <section className="rounded-2xl border border-white/[0.1] bg-gradient-to-br from-[#101a2d] to-[#09111f] p-6 sm:p-8">
            <div className="flex flex-col items-center justify-between gap-6 text-center sm:flex-row sm:text-left">
              <div>
                <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-violet-300">
                  Continuous Improvement
                </div>

                <h2 className="mt-2 text-xl font-semibold text-white">
                  Knowledge Gap Alerts & Telemetry
                </h2>

                <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-400">
                  A high knowledge gap rate highlights missing documentation or undocumented incident types, indicating where technical teams should author new runbooks.
                </p>
              </div>

              <div className="shrink-0 rounded-2xl border border-violet-400/20 bg-violet-500/[0.08] px-6 py-5">
                <div className="text-3xl font-semibold text-violet-200">
                  {feedbackTotal}
                </div>
                <div className="mt-1 text-[10px] uppercase tracking-[0.16em] text-slate-500">
                  Human signals recorded
                </div>
              </div>
            </div>
          </section>
        </div>
      )}
    </Layout>
  );
};

function AnalyticsMetric({
  label,
  value,
  sub,
  accent,
}: {
  label: string;
  value: number | string;
  sub: string;
  accent: "indigo" | "emerald" | "rose" | "amber";
}) {
  const styles = {
    indigo: {
      border: "border-indigo-400/35",
      value: "text-indigo-300",
      glow: "from-indigo-500/[0.12]",
    },
    emerald: {
      border: "border-emerald-400/35",
      value: "text-emerald-300",
      glow: "from-emerald-500/[0.1]",
    },
    rose: {
      border: "border-rose-400/35",
      value: "text-rose-300",
      glow: "from-rose-500/[0.1]",
    },
    amber: {
      border: "border-amber-400/35",
      value: "text-amber-300",
      glow: "from-amber-500/[0.1]",
    },
  }[accent];

  return (
    <section
      className={`rounded-2xl border ${styles.border} bg-gradient-to-br ${styles.glow} to-[#101a2d] p-5`}
    >
      <div className="text-[11px] font-semibold uppercase tracking-[0.15em] text-slate-500">
        {label}
      </div>

      <div className={`mt-5 text-4xl font-semibold tracking-tight ${styles.value}`}>
        {value}
      </div>

      <div className="mt-2 text-xs text-slate-400">{sub}</div>
    </section>
  );
}

function BreakdownCard({
  title,
  eyebrow,
  breakdown,
  type,
  emptyMessage,
}: {
  title: string;
  eyebrow: string;
  breakdown: Record<string, number>;
  type: "confidence" | "feedback";
  emptyMessage: string;
}) {
  const entries = Object.entries(breakdown);
  const total = entries.reduce((sum, [, count]) => sum + count, 0);

  return (
    <section className="rounded-2xl border border-white/[0.1] bg-gradient-to-br from-[#101a2d] to-[#09111f] p-6">
      <div className="mb-6">
        <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
          {eyebrow}
        </div>

        <h2 className="mt-2 text-lg font-semibold text-white">{title}</h2>
      </div>

      {entries.length === 0 ? (
        <div className="rounded-xl border border-dashed border-white/10 bg-black/10 px-4 py-8 text-center text-sm text-slate-500">
          {emptyMessage}
        </div>
      ) : (
        <div className="space-y-5">
          {entries.map(([key, count]) => {
            const percentageValue =
              total > 0 ? Math.round((count / total) * 100) : 0;

            return (
              <div key={key}>
                <div className="mb-2 flex items-center justify-between gap-3">
                  <span className="text-sm capitalize text-slate-300">
                    {formatLabel(key)}
                  </span>

                  <span className="text-sm font-semibold text-white">
                    {count}
                  </span>
                </div>

                <div className="h-2 overflow-hidden rounded-full bg-slate-800">
                  <div
                    className={`h-full rounded-full bg-gradient-to-r ${getBarColor(
                      key,
                      type
                    )}`}
                    style={{ width: `${percentageValue}%` }}
                  />
                </div>

                <div className="mt-1 text-[11px] text-slate-500">
                  {percentageValue}% of recorded data
                </div>
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}

function percentage(value: number, total: number) {
  if (!total) return "No feedback yet";
  return `${((value / total) * 100).toFixed(1)}% of feedback`;
}

function formatLabel(value: string) {
  return value.replaceAll("_", " ");
}

function getBarColor(key: string, type: "confidence" | "feedback") {
  if (type === "confidence") {
    if (key === "high") return "from-violet-500 to-indigo-400";
    if (key === "medium") return "from-cyan-400 to-blue-500";
    return "from-slate-500 to-slate-400";
  }

  if (key === "helpful") return "from-emerald-500 to-cyan-400";
  if (key === "not_helpful") return "from-rose-500 to-orange-400";
  return "from-amber-400 to-orange-500";
}

export default Page;