import React from "react";
import Link from "next/link";
import { useRouter } from "next/router";
import { ENGINE_VIEWS, EngineDot, engineTooltip } from "@/components/EngineStatus";
import { useEngineStatus } from "@/lib/useEngineStatus";

const navItems = [
  { href: "/search", label: "Solution Finder", icon: "search" },
  { href: "/knowledge", label: "Knowledge Library", icon: "library" },
  { href: "/feedback", label: "Feedback", icon: "feedback" },
  { href: "/audit", label: "Audit Trail", icon: "audit" },
  { href: "/analytics", label: "Impact Analytics", icon: "analytics" },
];

function SolviaMark() {
  return (
    <div className="relative flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-cyan-400 via-blue-500 to-violet-600 shadow-lg shadow-blue-950/40">
      <svg
        width="25"
        height="25"
        viewBox="0 0 24 24"
        fill="none"
        stroke="white"
        strokeWidth="1.6"
      >
        <path d="M12 3 4.5 7.2v9.6L12 21l7.5-4.2V7.2L12 3Z" />
        <path d="m4.5 7.2 7.5 4.4 7.5-4.4M12 11.6V21" />
        <path d="m8.2 5.1 7.5 4.3v5.2l-3.7 2.1-3.8-2.1V9.4l3.8-2.2" opacity=".75" />
      </svg>
    </div>
  );
}

function SidebarIcon({
  name,
  active,
}: {
  name: string;
  active: boolean;
}) {
  const stroke = active ? "#ffffff" : "currentColor";

  if (name === "library") {
    return (
      <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke={stroke} strokeWidth="1.8">
        <path d="M5 4h10v16H5z" />
        <path d="M9 4v16M15 7h4v13h-4" />
      </svg>
    );
  }

  if (name === "search") {
    return (
      <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke={stroke} strokeWidth="1.8">
        <circle cx="11" cy="11" r="7.5" />
        <path d="m20 20-3.6-3.6" />
        <path d="M11 8v6M8 11h6" opacity=".7" />
      </svg>
    );
  }

  if (name === "feedback") {
    return (
      <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke={stroke} strokeWidth="1.8">
        <path d="m4 17 5-5 3 3 8-8" />
        <path d="M16 7h4v4" />
        <path d="M4 20h16" opacity=".5" />
      </svg>
    );
  }

  if (name === "audit") {
    return (
      <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke={stroke} strokeWidth="1.8">
        <path d="M7 3h8l4 4v14H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2Z" />
        <path d="M15 3v5h4M8.5 12h5M8.5 16h5" />
      </svg>
    );
  }

  return (
    <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke={stroke} strokeWidth="1.8">
      <path d="M4 19V9M10 19V5M16 19v-8M22 19V3" />
      <path d="M3 21h20" opacity=".5" />
    </svg>
  );
}

function Sidebar() {
  const router = useRouter();
  const engine = useEngineStatus();

  return (
    <aside className="flex h-screen w-72 shrink-0 flex-col overflow-hidden border-r border-white/[0.08] bg-[#030711]">
      <div className="border-b border-white/[0.08] px-7 py-7">
        <div className="flex items-center gap-3">
          <SolviaMark />

          <div className="min-w-0">
            <div className="text-[22px] font-semibold tracking-tight text-white">
              SOLVIA
            </div>

            <div className="mt-0.5 whitespace-nowrap text-[10px] font-medium tracking-[0.08em] text-slate-400">
              INTELLIGENT · SOLUTION DISCOVERY
            </div>
          </div>
        </div>
      </div>

      <nav className="flex-1 px-4 py-8">
        <div className="mb-4 px-4 text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500">
          Navigation
        </div>

        <div className="space-y-2">
          {navItems.map((item) => {
            const active = router.pathname === item.href;

            return (
              <Link
                key={item.href}
                href={item.href}
                className={[
                  "group relative flex items-center gap-3 rounded-xl px-4 py-3.5 text-sm font-medium transition-all",
                  active
                    ? "bg-gradient-to-r from-indigo-600/35 via-blue-600/20 to-transparent text-white shadow-inner shadow-indigo-500/10"
                    : "text-slate-400 hover:bg-white/[0.045] hover:text-white",
                ].join(" ")}
              >
                {active && (
                  <span className="absolute bottom-2 left-0 top-2 w-0.5 rounded-r-full bg-gradient-to-b from-cyan-300 to-violet-500" />
                )}

                <span
                  className={
                    active
                      ? "text-cyan-300"
                      : "text-slate-500 group-hover:text-slate-300"
                  }
                >
                  <SidebarIcon name={item.icon} active={active} />
                </span>

                <span>{item.label}</span>
              </Link>
            );
          })}
        </div>
      </nav>

      <div className="space-y-5 px-5 pb-6">
        <div className="border-t border-white/[0.08] pt-5">
          <div className="mb-3 px-2 text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500">
            Engine Status
          </div>

          <div
            className="flex items-center gap-2 px-2 text-xs text-slate-300"
            title={engineTooltip(engine)}
          >
            <EngineDot state={engine.state} />
            <span>Engine Status:</span>
            <span className={`font-semibold ${ENGINE_VIEWS[engine.state].text}`}>
              {ENGINE_VIEWS[engine.state].label}
            </span>
          </div>
          <p className="mt-2 px-2 text-[11px] leading-4 text-slate-500">
            {ENGINE_VIEWS[engine.state].description}
          </p>
        </div>

        <div className="rounded-xl border border-white/[0.1] bg-white/[0.035] p-4">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-full bg-gradient-to-br from-slate-300 to-slate-500 text-sm font-bold text-slate-900">
              S
            </div>

            <div className="min-w-0 flex-1">
              <div className="truncate text-sm font-medium text-white">
                SOLVIA Operator
              </div>

              <div className="mt-0.5 text-[11px] text-slate-500">
                Local enterprise workspace
              </div>
            </div>

            <span className="text-slate-500">⌄</span>
          </div>
        </div>
      </div>
    </aside>
  );
}

type LayoutProps = {
  children: React.ReactNode;
  fullWidth?: boolean;
};

function MobileNav() {
  const router = useRouter();

  return (
    <nav className="flex gap-2 overflow-x-auto border-b border-white/[0.08] bg-[#030711] px-4 py-3 md:hidden">
      {navItems.map((item) => {
        const active = router.pathname === item.href;
        return (
          <Link
            key={item.href}
            href={item.href}
            className={[
              "whitespace-nowrap rounded-full px-3 py-1.5 text-xs font-medium",
              active ? "bg-indigo-500/30 text-white" : "text-slate-400",
            ].join(" ")}
          >
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}

export default function Layout({
  children,
  fullWidth = false,
}: LayoutProps) {
  return (
    <div className="h-screen overflow-hidden bg-[#030711] text-slate-100 antialiased">
      <div className="flex h-full">
        <Sidebar />

        <div className="flex min-w-0 flex-1 flex-col">
          <MobileNav />
          <main className="min-w-0 flex-1 overflow-y-auto px-5 py-6 sm:px-7 lg:px-9 lg:py-8">
            <div
              className={
                fullWidth
                  ? "w-full max-w-none"
                  : "mx-auto w-full max-w-[1440px]"
              }
            >
              {children}
            </div>
          </main>
        </div>
      </div>
    </div>
  );
}