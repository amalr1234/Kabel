import React, { useState, useEffect } from "react";
import type { NextPage } from "next";
import Layout from "@/components/Layout";
import LoadingState from "@/components/LoadingState";
import ErrorAlert from "@/components/ErrorAlert";
import { api, errorMessage, type AuditEntry } from "@/lib/api";

const Page: NextPage = () => {
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [limit] = useState(50);
  const [offset, setOffset] = useState(0);
  const [eventType, setEventType] = useState("");

  const load = async () => {
    setLoading(true);
    setError(null);

    try {
      const res = await api.getAudit(limit, offset, eventType || null);
      setEntries(res.entries);
      setTotal(res.total);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, [limit, offset, eventType]);

  const canGoBack = offset > 0;
  const canGoForward = offset + entries.length < total;

  const formatTime = (iso: string) => {
    try {
      return new Date(iso).toLocaleString(undefined, {
        year: "numeric",
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return iso;
    }
  };

  return (
    <Layout>
      <section className="mb-8">
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-3xl font-semibold tracking-tight text-white">
            Audit Trail
          </h1>

          <span className="rounded-full border border-violet-400/25 bg-violet-400/10 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-violet-300">
            Traceability
          </span>
        </div>

        <p className="mt-3 max-w-3xl text-sm leading-7 text-slate-400">
          Every SOLVIA action is recorded. Review solution generation, feedback
          activity and system events from one auditable timeline.
        </p>
      </section>

      <section className="mb-6 rounded-2xl border border-indigo-400/30 bg-gradient-to-br from-[#111b30] via-[#0d1628] to-[#08111f] p-5 shadow-[0_0_35px_rgba(79,70,229,0.05)] sm:p-6">
        <div className="mb-5 flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
              Event stream
            </div>

            <h2 className="mt-2 text-lg font-semibold text-white">
              System activity
            </h2>

            <p className="mt-1 text-sm text-slate-500">
              Filter recorded actions by event type.
            </p>
          </div>

          <div className="rounded-xl border border-white/10 bg-white/[0.04] px-4 py-3 text-right">
            <div className="text-2xl font-semibold text-cyan-300">
              {total}
            </div>
            <div className="text-[10px] uppercase tracking-[0.14em] text-slate-500">
              Total events
            </div>
          </div>
        </div>

        <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
          <div className="min-w-0 flex-1">
            <label
              htmlFor="eventType"
              className="mb-2 block text-xs font-semibold uppercase tracking-[0.12em] text-slate-400"
            >
              Event type
            </label>

            <select
              id="eventType"
              value={eventType}
              onChange={(e) => {
                setEventType(e.target.value);
                setOffset(0);
              }}
              className="w-full rounded-xl border border-white/10 bg-[#030817] px-4 py-3 text-sm text-white outline-none transition focus:border-indigo-400 focus:ring-4 focus:ring-indigo-500/10"
            >
              <option value="">All event types</option>
              <option value="solution_generated">
                Solution generated
              </option>
              <option value="feedback_recorded">
                Feedback recorded
              </option>
            </select>
          </div>

          <div className="rounded-xl border border-emerald-400/20 bg-emerald-400/[0.05] px-4 py-3 text-xs text-emerald-300">
            Showing {entries.length} of {total} records
          </div>
        </div>
      </section>

      {loading && <LoadingState message="Loading audit trail..." />}

      {error && <ErrorAlert message={error} onRetry={load} />}

      {!loading && !error && entries.length === 0 && (
        <EmptyState hasFilter={Boolean(eventType)} />
      )}

      {!loading && !error && entries.length > 0 && (
        <>
          <section className="relative">
            <div className="absolute bottom-5 left-[19px] top-5 w-px bg-gradient-to-b from-indigo-400/50 via-cyan-400/20 to-transparent" />

            <div className="space-y-4">
              {entries.map((entry) => (
                <AuditCard
                  key={entry.id}
                  entry={entry}
                  formatTime={formatTime}
                />
              ))}
            </div>
          </section>

          <div className="mt-6 flex flex-col gap-4 border-t border-white/[0.08] pt-5 sm:flex-row sm:items-center sm:justify-between">
            <div className="text-xs text-slate-500">
              {total > entries.length
                ? `Showing ${offset + 1}–${offset + entries.length} of ${total} events`
                : `Showing all ${total} events`}
            </div>

            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => setOffset((current) => Math.max(0, current - limit))}
                disabled={!canGoBack}
                className="rounded-xl border border-white/10 bg-white/[0.03] px-4 py-2.5 text-sm text-slate-300 transition hover:bg-white/[0.07] disabled:cursor-not-allowed disabled:opacity-40"
              >
                Previous
              </button>

              <button
                type="button"
                onClick={() => setOffset((current) => current + limit)}
                disabled={!canGoForward}
                className="rounded-xl border border-white/10 bg-white/[0.03] px-4 py-2.5 text-sm text-slate-300 transition hover:bg-white/[0.07] disabled:cursor-not-allowed disabled:opacity-40"
              >
                Next
              </button>
            </div>
          </div>
        </>
      )}
    </Layout>
  );
};

function AuditCard({
  entry,
  formatTime,
}: {
  entry: AuditEntry;
  formatTime: (iso: string) => string;
}) {
  const event = getEventPresentation(entry.event_type);

  return (
    <article className="relative ml-0 rounded-2xl border border-white/[0.1] bg-gradient-to-br from-[#101a2d] to-[#09111f] p-5 pl-16 transition hover:border-indigo-400/30 sm:p-6 sm:pl-20">
      <div
        className={`absolute left-0 top-5 flex h-10 w-10 items-center justify-center rounded-xl border sm:left-0 ${event.iconClass}`}
      >
        <span className="text-sm font-bold">{event.icon}</span>
      </div>

      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span
              className={`rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] ${event.badgeClass}`}
            >
              {event.label}
            </span>

            <span className="text-xs text-slate-600">Event #{entry.id}</span>
          </div>

          <p className="mt-4 break-words text-sm leading-6 text-slate-300">
            {entry.detail}
          </p>
        </div>

        <div className="shrink-0 text-left lg:text-right">
          <div className="text-xs font-medium text-slate-300">
            {entry.actor}
          </div>

          <div className="mt-1 text-xs text-slate-500">
            {formatTime(entry.created_at)}
          </div>
        </div>
      </div>
    </article>
  );
}

function getEventPresentation(eventType: string) {
  if (eventType === "solution_generated") {
    return {
      label: "Solution generated",
      icon: "✦",
      iconClass:
        "border-indigo-400/30 bg-indigo-500/15 text-indigo-300",
      badgeClass:
        "border-indigo-400/25 bg-indigo-400/10 text-indigo-300",
    };
  }

  if (eventType === "feedback_recorded") {
    return {
      label: "Feedback recorded",
      icon: "✓",
      iconClass:
        "border-emerald-400/30 bg-emerald-400/10 text-emerald-300",
      badgeClass:
        "border-emerald-400/25 bg-emerald-400/10 text-emerald-300",
    };
  }

  return {
    label: eventType.replaceAll("_", " "),
    icon: "•",
    iconClass:
      "border-cyan-400/30 bg-cyan-400/10 text-cyan-300",
    badgeClass:
      "border-cyan-400/25 bg-cyan-400/10 text-cyan-300",
  };
}

function EmptyState({ hasFilter }: { hasFilter: boolean }) {
  return (
    <section className="rounded-2xl border border-white/[0.1] bg-gradient-to-br from-[#101a2d] to-[#09111f] px-6 py-16 text-center">
      <div className="mx-auto mb-5 flex h-16 w-16 items-center justify-center rounded-2xl border border-violet-400/20 bg-violet-500/10 text-violet-300">
        <svg
          width="28"
          height="28"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
        >
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
          <path d="M14 2v6h6M8 13h8M8 17h5" />
        </svg>
      </div>

      <h2 className="text-xl font-semibold text-white">
        {hasFilter ? "No matching events" : "No audit records yet"}
      </h2>

      <p className="mx-auto mt-2 max-w-lg text-sm leading-6 text-slate-400">
        {hasFilter
          ? "Try selecting a different event type or clear the current filter."
          : "Audit entries appear when SOLVIA generates solutions or records feedback."}
      </p>
    </section>
  );
}

export default Page;