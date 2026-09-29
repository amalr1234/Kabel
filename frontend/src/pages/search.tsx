import { useEffect, useState, type FormEvent } from "react";
import type { NextPage } from "next";
import Link from "next/link";
import Layout from "@/components/Layout";
import LoadingState from "@/components/LoadingState";
import ErrorAlert from "@/components/ErrorAlert";
import ResultsPanel from "@/components/ResultsPanel";
import { ENGINE_VIEWS, EngineDot, engineTooltip } from "@/components/EngineStatus";
import {
  API_BASE_URL,
  api,
  errorMessage,
  type SolutionQuery,
  type SolutionResponse,
} from "@/lib/api";
import { CATEGORIES, PRIORITIES, STORAGE_KEYS, SYSTEMS } from "@/lib/constants";
import { useEngineStatus, type EngineState } from "@/lib/useEngineStatus";

const BACKEND_LABELS: Record<EngineState, string> = {
  checking: "Checking backend...",
  live: "Connected to backend",
  demo: "Connected to backend (demo mode)",
  degraded: "Connected, but some services are failing",
  offline: "Backend unreachable",
};

function persist(key: string, value: string | null) {
  try {
    if (value) {
      window.localStorage.setItem(key, value);
    } else {
      window.localStorage.removeItem(key);
    }
  } catch (persistError) {
    console.warn(`Unable to persist ${key}`, persistError);
  }
}

type SearchDraft = {
  query: string;
  system: string;
  category: string;
  priority: string;
};

const Page: NextPage = () => {
  const [query, setQuery] = useState("");
  const [system, setSystem] = useState("");
  const [category, setCategory] = useState("");
  const [priority, setPriority] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [solution, setSolution] = useState<SolutionResponse | null>(null);
  const [isHydrated, setIsHydrated] = useState(false);
  const engine = useEngineStatus();
  const engineView = ENGINE_VIEWS[engine.state];

  const resetForm = () => {
    setQuery("");
    setSystem("");
    setCategory("");
    setPriority("");
  };

  useEffect(() => {
    try {
      const savedDraft = window.localStorage.getItem(STORAGE_KEYS.searchDraft);
      const savedSolution = window.localStorage.getItem(STORAGE_KEYS.lastSolution);

      if (savedDraft) {
        const draft = JSON.parse(savedDraft) as Partial<SearchDraft>;
        setQuery(draft.query ?? "");
        setSystem(draft.system ?? "");
        setCategory(draft.category ?? "");
        setPriority(draft.priority ?? "");
      }

      if (savedSolution) {
        setSolution(JSON.parse(savedSolution) as SolutionResponse);
      }
    } catch (restoreError) {
      console.warn("Unable to restore previous search", restoreError);
    } finally {
      setIsHydrated(true);
    }
  }, []);

  useEffect(() => {
    if (!isHydrated) return;
    const hasDraft = Boolean(query.trim() || system || category || priority);
    persist(
      STORAGE_KEYS.searchDraft,
      hasDraft ? JSON.stringify({ query, system, category, priority } satisfies SearchDraft) : null
    );
  }, [query, system, category, priority, isHydrated]);

  useEffect(() => {
    if (isHydrated) persist(STORAGE_KEYS.lastSolution, solution ? JSON.stringify(solution) : null);
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
      resetForm();
    } catch (err) {
      setError(errorMessage(err));
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

          <span
            className={`ml-auto inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs ${engineView.pill} ${engineView.text}`}
            title={engineTooltip(engine)}
          >
            <EngineDot state={engine.state} className="h-1.5 w-1.5" />
            Engine {engineView.label.toLowerCase()}
          </span>
        </div>

        <p className="mt-3 max-w-3xl text-sm leading-7 text-slate-400">
          Describe the issue and SOLVIA will search the enterprise knowledge
          library, including historical tickets, SAP knowledge, and
          documentation, to retrieve relevant evidence and propose a grounded
          remediation path.
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
            <EngineDot state={engine.state} className="h-1.5 w-1.5" />
            {BACKEND_LABELS[engine.state]}
            <span className="hidden text-slate-700 sm:inline">·</span>
            <span className="hidden sm:inline">{API_BASE_URL}</span>
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
      <Link
        href="/knowledge"
        className="mt-5 inline-flex text-sm font-semibold text-cyan-300"
      >
        Open Knowledge Library →
      </Link>
    </div>
  );
}

export default Page;