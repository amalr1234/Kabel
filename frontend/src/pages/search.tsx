import { useEffect, useState, type FormEvent } from "react";
import type { NextPage } from "next";
import Layout from "@/components/Layout";
import LoadingState from "@/components/LoadingState";
import ErrorAlert from "@/components/ErrorAlert";
import ResultsPanel from "@/components/ResultsPanel";
import { api, type SolutionQuery } from "@/lib/api";

const PRIORITIES = ["low", "medium", "high", "critical"];

const CATEGORIES = [
  "authentication",
  "performance",
  "installation",
  "upgrade",
  "authorization",
  "backup",
  "transport",
  "basis",
];

const SYSTEMS = [
  "SAP",
  "S/4HANA",
  "ABAP",
  "HANA",
  "NetWeaver",
  "Fiori",
  "CPI",
  "Other",
];

const Page: NextPage = () => {
  const [query, setQuery] = useState("");
  const [system, setSystem] = useState("");
  const [category, setCategory] = useState("");
  const [priority, setPriority] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [solution, setSolution] = useState<
    Awaited<ReturnType<typeof api.solve>> | null
  >(null);

    const [isHydrated, setIsHydrated] = useState(false);

  useEffect(() => {
    try {
      const savedQuery = window.localStorage.getItem("solvia:last-query");
      const savedSolution = window.localStorage.getItem(
        "solvia:last-solution"
      );

      if (savedQuery) {
        setQuery(savedQuery);
      }

      if (savedSolution) {
        setSolution(
          JSON.parse(savedSolution) as Awaited<ReturnType<typeof api.solve>>
        );
      }
    } catch (restoreError) {
      console.warn("Unable to restore previous search", restoreError);
    } finally {
      setIsHydrated(true);
    }
  }, []);

  useEffect(() => {
    if (!isHydrated) return;

    try {
      if (query.trim()) {
        window.localStorage.setItem("solvia:last-query", query);
      } else {
        window.localStorage.removeItem("solvia:last-query");
      }
    } catch (persistError) {
      console.warn("Unable to persist search query", persistError);
    }
  }, [query, isHydrated]);

  useEffect(() => {
    if (!isHydrated) return;

    try {
      if (solution) {
        window.localStorage.setItem(
          "solvia:last-solution",
          JSON.stringify(solution)
        );
      } else {
        window.localStorage.removeItem("solvia:last-solution");
      }
    } catch (persistError) {
      console.warn("Unable to persist search solution", persistError);
    }
  }, [solution, isHydrated]);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    if (!query.trim()) return;

    setLoading(true);
    setError(null);
    setSolution(null);

    const payload: SolutionQuery = {
      query: query.trim(),
      system: system || null,
      category: category || null,
      priority: priority || null,
    };

    try {
      const result = await api.solve(payload);
      setSolution(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <Layout>
      <section className="mb-8">
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-3xl font-semibold tracking-tight text-white">
            Solution Finder
          </h1>

          <span className="rounded-full border border-indigo-400/30 bg-indigo-500/10 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-indigo-300">
            RAG
          </span>

          <span className="ml-auto inline-flex items-center gap-2 rounded-full border border-emerald-400/20 bg-emerald-400/5 px-3 py-1.5 text-xs text-emerald-300">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.9)]" />
            Engine live
          </span>
        </div>

        <p className="mt-3 max-w-3xl text-sm leading-7 text-slate-400">
          Describe the issue and SOLVIA will search the enterprise knowledge
          library — historical tickets, SAP knowledge, and documentation — to
          retrieve relevant evidence and propose a grounded remediation path.
        </p>
      </section>

      <form
        onSubmit={handleSubmit}
        className="relative mb-7 overflow-hidden rounded-2xl border border-indigo-400/50 bg-gradient-to-br from-[#111a2d] via-[#0d1628] to-[#08111f] p-5 shadow-[0_0_45px_rgba(79,70,229,0.08)] sm:p-7"
      >
        <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-cyan-400 to-transparent" />

        <div className="mb-6 flex items-center justify-between gap-4">
          <div>
            <label
              htmlFor="query"
              className="text-sm font-semibold text-slate-100"
            >
              Describe the issue{" "}
              <span className="text-rose-400">*</span>
            </label>
            <p className="mt-1 text-xs text-slate-500">
              Include the system, symptoms and any relevant error message.
            </p>
          </div>

          <span className="hidden rounded-lg border border-white/10 bg-white/[0.04] px-3 py-2 text-xs text-slate-500 sm:inline-flex">
            Evidence-grounded search
          </span>
        </div>

        <div className="relative">
          <textarea
            id="query"
            rows={5}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Example: User cannot login to SAP after password reset. System shows Authentication failed even though the password is correct."
            className="h-14 min-h-14 w-full resize-none overflow-y rounded-xl border border-white/10 bg-[#030817]/90 px-4 py-3 text-sm leading-7 text-white placeholder-slate-600 outline-none transition focus:border-indigo-400 focus:ring-4 focus:ring-indigo-500/10"
          />

          <div className="pointer-events-none absolute bottom-4 right-4 text-indigo-300/70">
            <svg
              width="20"
              height="20"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.7"
            >
              <path d="M12 3v18M3 12h18" />
              <path d="m5 5 14 14M19 5 5 19" opacity=".45" />
            </svg>
          </div>
        </div>

        <div className="mt-5 grid grid-cols-1 gap-4 md:grid-cols-3">
          <FilterSelect
            id="system"
            label="System"
            value={system}
            onChange={setSystem}
            placeholder="All systems"
            options={SYSTEMS}
          />

          <FilterSelect
            id="category"
            label="Category"
            value={category}
            onChange={setCategory}
            placeholder="All categories"
            options={CATEGORIES}
          />

          <FilterSelect
            id="priority"
            label="Priority"
            value={priority}
            onChange={setPriority}
            placeholder="Any priority"
            options={PRIORITIES}
          />
        </div>

        <div className="mt-6 flex flex-col gap-4 border-t border-white/[0.08] pt-5 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-2 text-xs text-slate-500">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
            Connected to local backend
            <span className="hidden text-slate-700 sm:inline">·</span>
            <span className="hidden sm:inline">
              {process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}
            </span>
          </div>

          <button
            type="submit"
            disabled={loading || !query.trim()}
            className="inline-flex items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-violet-600 via-indigo-500 to-cyan-400 px-6 py-3 text-sm font-semibold text-white shadow-lg shadow-indigo-950/40 transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {loading ? (
              <>
                <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
                Scanning knowledge graph...
              </>
            ) : (
              <>
                <svg
                  width="17"
                  height="17"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                >
                  <path d="m21 21-5.2-5.2" />
                  <circle cx="10.5" cy="10.5" r="6.5" />
                </svg>
                Find Solutions
              </>
            )}
          </button>
        </div>
      </form>

      {loading && <LoadingState message="Scanning knowledge graph..." />}

      {error && <ErrorAlert message={error} onRetry={() => setError(null)} />}

      {solution && <ResultsPanel solution={solution} />}

      {!loading && !error && !solution && <EmptyState />}
    </Layout>
  );
};

function FilterSelect({
  id,
  label,
  value,
  onChange,
  placeholder,
  options,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
  options: string[];
}) {
  return (
    <div>
      <label
        htmlFor={id}
        className="mb-2 block text-xs font-semibold uppercase tracking-[0.12em] text-slate-400"
      >
        {label}
      </label>

      <select
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-xl border border-white/10 bg-[#030817] px-3.5 py-3 text-sm text-white outline-none transition focus:border-indigo-400 focus:ring-4 focus:ring-indigo-500/10"
      >
        <option value="">{placeholder}</option>
        {options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    </div>
  );
}

function EmptyState() {
  return (
    <div className="rounded-2xl border border-white/[0.08] bg-gradient-to-br from-[#101a2d] to-[#09111f] px-6 py-16 text-center">
      <div className="mx-auto mb-5 flex h-16 w-16 items-center justify-center rounded-2xl border border-indigo-400/20 bg-indigo-500/10 text-indigo-300">
        <svg
          width="28"
          height="28"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
        >
          <circle cx="11" cy="11" r="7.5" />
          <path d="m20 20-3.6-3.6" />
        </svg>
      </div>

      <h2 className="text-lg font-semibold text-white">
        Ready to find a solution
      </h2>

      <p className="mx-auto mt-2 max-w-lg text-sm leading-6 text-slate-400">
        Enter an issue above and SOLVIA will retrieve evidence-based
        recommendations from the enterprise knowledge library.
      </p>
    </div>
  );
}

export default Page;