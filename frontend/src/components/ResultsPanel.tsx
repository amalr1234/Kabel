import React from "react";
import type { SolutionResponse } from "@/lib/api";

interface ResultsPanelProps {
  solution: SolutionResponse;
}

export default function ResultsPanel({ solution }: ResultsPanelProps) {
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 items-stretch gap-6 xl:grid-cols-[minmax(0,1fr)_390px]">
        {/* Left column */}
        <main className="min-w-0 space-y-6">
          <ReasoningSection reasoning={solution.reasoning} />

          <SolutionHeader solution={solution} />

          <ExecutionBlueprint
            blueprint={solution.execution_blueprint}
          />
        </main>

        {/* Right column */}
        <aside className="flex h-full min-w-0 flex-col gap-6">
          <ConfidencePanel
            breakdown={solution.confidence_breakdown}
          />

          <HumanReviewBanner
            requiresReview={solution.requires_human_review}
          />

          {/* Fill the remaining height so it aligns with Execution Blueprint */}
          <div className="flex min-h-0 flex-1">
            <div className="w-full">
              <KnowledgeGaps gaps={solution.knowledge_gaps} />
            </div>
          </div>
        </aside>

        {/* Full-width AI Evidence */}
        <div className="min-w-0 xl:col-span-2">
          <EvidenceSection evidence={solution.evidence} />
        </div>
      </div>
    </div>
  );
}

function SolutionHeader({ solution }: { solution: SolutionResponse }) {
  const score = Math.max(0, Math.min(100, solution.match_score));

  return (
    <section className="relative overflow-hidden rounded-2xl border border-white/[0.1] bg-gradient-to-br from-[#111b30] via-[#0d1628] to-[#08111f] p-5 shadow-[0_0_40px_rgba(79,70,229,0.07)] sm:p-7">
      <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-cyan-400 to-transparent" />

      <div className="flex flex-col gap-6 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <div className="mb-3 text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500">
            Recommended solution
          </div>

          <h2 className="max-w-3xl text-2xl font-semibold leading-tight tracking-tight text-white sm:text-3xl">
            {solution.solution_title}
          </h2>

          <div className="mt-5 flex flex-wrap items-center gap-2">
            <span className="inline-flex items-center gap-2 rounded-full border border-indigo-400/30 bg-indigo-500/10 px-3 py-1.5 text-xs font-semibold uppercase tracking-wider text-indigo-200">
              <span className="h-1.5 w-1.5 rounded-full bg-indigo-300" />
              {solution.confidence}
            </span>

            {solution.requires_human_review && (
              <span className="inline-flex items-center gap-2 rounded-full border border-amber-400/25 bg-amber-400/10 px-3 py-1.5 text-xs text-amber-200">
                Human review required
              </span>
            )}
          </div>
        </div>

        <ScoreRing score={score} />
      </div>
    </section>
  );
}

function ScoreRing({ score }: { score: number }) {
  const radius = 42;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (score / 100) * circumference;

  return (
    <div className="shrink-0">
      <div className="relative h-28 w-28">
        <svg
          className="-rotate-90"
          width="112"
          height="112"
          viewBox="0 0 112 112"
          fill="none"
        >
          <circle
            cx="56"
            cy="56"
            r={radius}
            stroke="rgba(71, 85, 105, 0.35)"
            strokeWidth="8"
          />

          <circle
            cx="56"
            cy="56"
            r={radius}
            stroke="url(#scoreGradient)"
            strokeWidth="8"
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
          />

          <defs>
            <linearGradient
              id="scoreGradient"
              x1="10"
              y1="10"
              x2="100"
              y2="100"
            >
              <stop stopColor="#7c3aed" />
              <stop offset="0.55" stopColor="#4f8cff" />
              <stop offset="1" stopColor="#22d3ee" />
            </linearGradient>
          </defs>
        </svg>

        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-2xl font-semibold text-white">
            {score}
            <span className="text-sm text-slate-400">%</span>
          </span>

          <span className="text-[10px] text-slate-500">
            Match score
          </span>
        </div>
      </div>
    </div>
  );
}


function ConfidencePanel({
  breakdown,
}: {
  breakdown: SolutionResponse["confidence_breakdown"];
}) {
  return (
    <section className="rounded-2xl border border-white/[0.1] bg-gradient-to-br from-[#101a2d] to-[#09111f] p-6">
      <div className="mb-6 flex items-center justify-between">
        <div className="text-base font-semibold text-white">
          Confidence breakdown
        </div>

        <span className="text-xs text-slate-500">AI signal</span>
      </div>

      <div className="space-y-5">
        <ConfidenceBar
          label="Semantic similarity"
          value={breakdown.semantic_similarity}
          color="from-violet-500 to-indigo-400"
        />

        <ConfidenceBar
          label="Historical success"
          value={breakdown.historical_success_rate}
          color="from-emerald-500 to-cyan-400"
        />

        <ConfidenceBar
          label="Source reliability"
          value={breakdown.source_reliability}
          color="from-amber-500 to-orange-400"
        />

        <ConfidenceBar
          label="Recency factor"
          value={breakdown.recency_factor}
          color="from-blue-500 to-cyan-400"
        />
      </div>
    </section>
  );
}

function ConfidenceBar({
  label,
  value,
  color,
}: {
  label: string;
  value: number;
  color: string;
}) {
  const safeValue = Math.max(0, Math.min(100, value));

  return (
    <div>
      <div className="mb-2 flex items-center justify-between gap-3 text-sm">
        <span className="text-slate-400">{label}</span>
        <span className="font-semibold text-slate-200">
          {safeValue}%
        </span>
      </div>

      <div className="h-1.5 overflow-hidden rounded-full bg-slate-800">
        <div
          className={`h-full rounded-full bg-gradient-to-r ${color}`}
          style={{ width: `${safeValue}%` }}
        />
      </div>
    </div>
  );
}

function ReasoningSection({ reasoning }: { reasoning: string }) {
  return (
    <section className="rounded-2xl border border-white/[0.1] bg-gradient-to-br from-[#101a2d] to-[#09111f] p-5 sm:p-6">
      <SectionLabel>AI reasoning</SectionLabel>

      <div className="mt-4 flex gap-3">
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-indigo-400/25 bg-indigo-500/10 text-indigo-300">
          ✦
        </div>

        <p className="text-sm leading-7 text-slate-300">
          {reasoning}
        </p>
      </div>
    </section>
  );
}

function ExecutionBlueprint({
  blueprint,
}: {
  blueprint: string[];
}) {
  if (!blueprint.length) return null;

  return (
    <section className="rounded-2xl border border-white/[0.1] bg-gradient-to-br from-[#101a2d] to-[#09111f] p-5 sm:p-6">
      <SectionLabel>Execution blueprint</SectionLabel>

      <ol className="mt-5 space-y-0">
        {blueprint.map((step, index) => (
          <li key={`${step}-${index}`} className="relative flex gap-4 pb-5 last:pb-0">
            {index < blueprint.length - 1 && (
              <span className="absolute left-[15px] top-8 h-[calc(100%-16px)] w-px bg-slate-700" />
            )}

            <span className="relative z-10 flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-indigo-300/40 bg-indigo-500/25 text-xs font-semibold text-indigo-100">
              {index + 1}
            </span>

            <div className="pt-1 text-sm leading-6 text-slate-300">
              {step}
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}

function EvidenceSection({
  evidence,
}: {
  evidence: SolutionResponse["evidence"];
}) {
  if (!evidence.length) return null;

  return (
    <section className="min-h-[520px] rounded-2xl border border-white/[0.1] bg-gradient-to-br from-[#101a2d] to-[#09111f] p-5">
      <div className="mb-4 flex items-center justify-between gap-3">
        <div>
          <SectionLabel>AI evidence</SectionLabel>
          <p className="mt-1 text-xs text-slate-500">
            Sources supporting this recommendation
          </p>
        </div>

        <span className="rounded-full border border-cyan-400/20 bg-cyan-400/5 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wider text-cyan-300">
          Provenance
        </span>
      </div>

      <div className="space-y-3">
        {evidence.map((item, index) => (
          <EvidenceCard key={`${item.title}-${index}`} item={item} />
        ))}
      </div>
    </section>
  );
}

function EvidenceCard({
  item,
}: {
  item: SolutionResponse["evidence"][number];
}) {
  const safeMatchScore = Math.min(
    100,
    Math.max(0, Math.round(item.match_score))
  );

  const reliability =
    item.source_reliability == null
      ? null
      : Math.round(
          item.source_reliability <= 1
            ? item.source_reliability * 100
            : item.source_reliability
        );

  const sourceLabel = item.source || item.source_type;

  return (
    <article className="rounded-xl border border-white/[0.1] bg-[#030817]/80 p-3.5 transition hover:border-indigo-400/30 hover:bg-[#071126]">
      <div className="flex items-start gap-3">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-blue-600/80 to-indigo-500/70 text-xs font-bold text-white">
          {(item.source_type || "S")[0].toUpperCase()}
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              <h3 className="truncate text-sm font-semibold text-white">
                {item.title}
              </h3>

              <div className="mt-1 text-[11px] leading-5 text-slate-500">
                {sourceLabel}
                {item.ticket_id ? ` · ${item.ticket_id}` : ""}
                {item.document_id && item.document_id !== "N/A"
                  ? ` · ${item.document_id}`
                  : ""}
              </div>
            </div>

            <span className="shrink-0 rounded-md border border-emerald-400/20 bg-emerald-400/10 px-2 py-1 text-[10px] font-semibold text-emerald-300">
              {safeMatchScore}%
            </span>
          </div>

          <p className="mt-3 text-xs leading-5 text-slate-400">
            {item.snippet}
          </p>

          {reliability != null && (
            <div className="mt-2 text-[11px] text-emerald-300">
              Source reliability: {reliability}%
            </div>
          )}

          <p className="mt-3 border-t border-white/[0.06] pt-3 text-[11px] leading-5 text-slate-500">
            <span className="font-semibold text-cyan-300">
              Why it matters:
            </span>{" "}
            {item.reason}
          </p>
        </div>
      </div>
    </article>
  );
}

function KnowledgeGaps({ gaps }: { gaps: string[] }) {
  return (
    <section className="rounded-2xl border border-amber-400/25 bg-amber-400/[0.05] p-6">
      <SectionLabel className="text-amber-300">
        Knowledge gaps
      </SectionLabel>

      {gaps.length > 0 ? (
        <ul className="mt-5 space-y-4">
          {gaps.map((gap, index) => (
            <li
              key={`${gap}-${index}`}
              className="flex gap-3 text-sm leading-6 text-slate-300"
            >
              <span className="text-amber-300">—</span>
              <span>{gap}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-5 text-sm leading-6 text-emerald-300">
          No significant knowledge gaps identified for this recommendation.
        </p>
      )}
    </section>
  );
}

function HumanReviewBanner({
  requiresReview,
}: {
  requiresReview: boolean;
}) {
  if (!requiresReview) return null;

  return (
    <section className="rounded-2xl border border-amber-400/35 bg-gradient-to-r from-amber-400/[0.12] to-orange-400/[0.04] p-6">
      <div className="flex flex-col gap-4">
        <div className="flex items-start gap-3">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-amber-300/30 bg-amber-400/15 text-amber-300">
            !
          </div>

          <div className="min-w-0">
            <div className="text-sm font-semibold text-amber-200">
              Human review required
            </div>

            <p className="mt-1 text-xs leading-5 text-slate-300">
              SOLVIA recommends only. Review the evidence and validate the
              remediation before implementation.
            </p>
          </div>
        </div>

        <span className="inline-flex w-fit rounded-lg border border-amber-300/25 bg-amber-300/10 px-3 py-2 text-xs font-semibold text-amber-200">
          Validate before action
        </span>
      </div>
    </section>
  );
}

function SectionLabel({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={`text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400 ${className}`}
    >
      {children}
    </div>
  );
}