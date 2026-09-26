import React from "react";

interface MetricCardProps {
  label: string;
  value: string | number;
  sub?: string;
  variant?: "default" | "accent" | "success" | "warning" | "danger";
}

export default function MetricCard({ label, value, sub, variant = "default" }: MetricCardProps) {
  const borderColor =
    variant === "accent"
      ? "border-accent/40"
      : variant === "success"
      ? "border-success/40"
      : variant === "warning"
      ? "border-warning/40"
      : variant === "danger"
      ? "border-danger/40"
      : "border-surface-700";

  const valueColor =
    variant === "accent"
      ? "text-accent"
      : variant === "success"
      ? "text-success"
      : variant === "warning"
      ? "text-warning"
      : variant === "danger"
      ? "text-danger"
      : "text-white";

  return (
    <div className={`rounded-xl border ${borderColor} bg-panel p-5 transition-colors hover:bg-panel-hover`}>
      <div className="text-xs font-medium uppercase tracking-wider text-surface-500 mb-3">{label}</div>
      <div className={`text-3xl font-semibold tracking-tight ${valueColor}`}>{value}</div>
      {sub && <div className="mt-2 text-xs text-surface-400">{sub}</div>}
    </div>
  );
}
