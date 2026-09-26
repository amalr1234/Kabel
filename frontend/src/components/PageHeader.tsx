import React from "react";

interface PageHeaderProps {
  title: string;
  subtitle?: string;
  badge?: string;
}

export default function PageHeader({ title, subtitle, badge }: PageHeaderProps) {
  return (
    <div className="mb-8">
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-3 mb-2">
            <h1 className="text-2xl font-semibold tracking-tight text-white">{title}</h1>
            {badge && (
              <span className="inline-flex items-center rounded-full px-3 py-0.5 text-[11px] font-medium uppercase tracking-wider bg-accent/15 text-accent border border-accent/30">
                {badge}
              </span>
            )}
          </div>
          {subtitle && (
            <p className="text-sm text-surface-400 max-w-2xl leading-relaxed">{subtitle}</p>
          )}
        </div>
      </div>
    </div>
  );
}
