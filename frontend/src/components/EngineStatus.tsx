import React from "react";
import type { EngineStatus, EngineState } from "@/lib/useEngineStatus";

interface EngineView {
  label: string;
  description: string;
  dot: string;
  text: string;
  pill: string;
}

export const ENGINE_VIEWS: Record<EngineState, EngineView> = {
  checking: {
    label: "Checking...",
    description: "Contacting the SOLVIA backend.",
    dot: "bg-slate-500",
    text: "text-slate-400",
    pill: "border-white/10 bg-white/[0.04]",
  },
  live: {
    label: "Live",
    description: "Gemini, database and knowledge library are online.",
    dot: "bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.9)]",
    text: "text-emerald-300",
    pill: "border-emerald-400/20 bg-emerald-400/5",
  },
  demo: {
    label: "Demo mode",
    description: "No Gemini API key: placeholder embeddings and no AI generation.",
    dot: "bg-amber-400 shadow-[0_0_8px_rgba(251,191,36,0.8)]",
    text: "text-amber-300",
    pill: "border-amber-400/25 bg-amber-400/5",
  },
  degraded: {
    label: "Degraded",
    description: "Backend is up but the database or vector store is failing.",
    dot: "bg-orange-400 shadow-[0_0_8px_rgba(251,146,60,0.8)]",
    text: "text-orange-300",
    pill: "border-orange-400/25 bg-orange-400/5",
  },
  offline: {
    label: "Offline",
    description: "Cannot reach the SOLVIA backend.",
    dot: "bg-rose-500 shadow-[0_0_8px_rgba(244,63,94,0.8)]",
    text: "text-rose-300",
    pill: "border-rose-400/25 bg-rose-400/5",
  },
};

export function engineTooltip({ state, health }: EngineStatus): string {
  const view = ENGINE_VIEWS[state];
  const failing = Object.entries(health?.checks ?? {})
    .filter(([, check]) => !check.ok)
    .map(([name, check]) => `${name}: ${check.error ?? "failed"}`);
  return [view.description, ...failing].join("\n");
}

export function EngineDot({ state, className = "h-2 w-2" }: { state: EngineState; className?: string }) {
  return <span className={`${className} shrink-0 rounded-full ${ENGINE_VIEWS[state].dot}`} />;
}
