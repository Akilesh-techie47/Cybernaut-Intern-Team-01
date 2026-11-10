"use client";

/*!
 * Next.js - AeroDelay AI Premium Navigation
 *
 * Phase 5.3 fixes:
 *  - Active tab is derived from usePathname (no callback plumbing)
 *  - Home link now points to "/" (it previously pointed to "/home", a 404)
 *  - Real lucide-react icons instead of `lucide-*` icon-font classes,
 *    which rendered as empty elements (no icon font is loaded)
 *  - Fixed invalid Tailwind opacity `bg-navy-950/950` -> `/95`
 *  - TopNav shows live backend status (helps verify API availability)
 */

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import {
  Home,
  Map,
  Clock,
  BarChart3,
  Settings,
  Plane,
  Files,
} from "lucide-react";
import { api, describeApiError } from "../lib/api";

const TABS = [
  { key: "home", href: "/", label: "Home", icon: Home },
  { key: "tracking", href: "/tracking", label: "Tracking", icon: Map },
  { key: "prediction", href: "/prediction", label: "Predict", icon: Clock },
  { key: "batch", href: "/batch", label: "Batch", icon: Files },
  { key: "analytics", href: "/analytics", label: "Analytics", icon: BarChart3 },
  { key: "models", href: "/models", label: "Models", icon: Settings },
] as const;

function activeKeyFor(pathname: string): string {
  if (pathname === "/") return "home";
  const match = TABS.find(
    (t) => t.href !== "/" && pathname.startsWith(t.href),
  );
  return match ? match.key : "home";
}

/* ── Live backend status pill (shared by TopNav) ───────────────────────── */

function ApiStatusPill() {
  const [state, setState] = useState<"loading" | "online" | "offline">(
    "loading",
  );

  useEffect(() => {
    let cancelled = false;
    api
      .status()
      .then(() => {
        if (!cancelled) setState("online");
      })
      .catch(() => {
        if (!cancelled) setState("offline");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const label =
    state === "online"
      ? "API Online"
      : state === "offline"
        ? "API Offline"
        : "Checking…";
  const dot =
    state === "online"
      ? "bg-green-400"
      : state === "offline"
        ? "bg-red-500"
        : "bg-yellow-400 animate-pulse";

  return (
    <span
      data-testid="api-status"
      data-state={state}
      className="hidden lg:inline-flex items-center gap-2 px-3 py-1.5 rounded-full border border-navy-800 bg-navy-900/70 text-xs text-navy-300"
      title={
        state === "offline"
          ? `Backend unreachable: ${describeApiError(new Error("offline"))}`
          : "FastAPI backend connectivity"
      }
    >
      <span className={`w-2 h-2 rounded-full ${dot}`} aria-hidden="true" />
      {label}
    </span>
  );
}

/* ── Top bar navigation (desktop, md and up) ────────────────────────────── */

export function TopNav() {
  const pathname = usePathname();
  const active = activeKeyFor(pathname);

  return (
    <nav
      className="hidden md:block fixed top-0 inset-x-0 bg-navy-950/95 backdrop-blur-xl border-b border-navy-800 z-50"
      aria-label="Top navigation"
    >
      <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between gap-4 lg:gap-6">
        <div className="flex items-center gap-4 lg:gap-8 min-w-0">
          <Link
            href="/"
            aria-label="AeroDelay AI home"
            className="font-display-bold text-xl lg:text-2xl text-cyan-500 hover:text-cyan-400 transition-colors flex items-center gap-2 shrink-0"
          >
            <Plane className="w-6 h-6" aria-hidden="true" />
            {/* Wordmark hidden between md and lg so 6 tabs fit at 768px */}
            <span className="hidden lg:inline">AeroDelay AI</span>
          </Link>

          <ul className="hidden md:flex gap-1 lg:gap-2">
            {TABS.map((tab) => {
              const Icon = tab.icon;
              const isActive = active === tab.key;
              return (
                <li key={tab.key}>
                  <Link
                    href={tab.href}
                    aria-current={isActive ? "page" : undefined}
                    className={`flex items-center gap-1.5 lg:gap-2 px-2 lg:px-3 py-2 rounded-lg text-sm transition-colors ${
                      isActive
                        ? "text-cyan-400 bg-cyan-500/10 font-medium"
                        : "text-navy-400 hover:text-navy-200 hover:bg-navy-900/60"
                    }`}
                  >
                    <Icon className="w-4 h-4 shrink-0" aria-hidden="true" />
                    <span className="whitespace-nowrap break-words">
                      {tab.label}
                    </span>
                  </Link>
                </li>
              );
            })}
          </ul>
        </div>

        <ApiStatusPill />
      </div>
    </nav>
  );
}

/* ── Bottom navigation bar (mobile first) ───────────────────────────────── */

export function BottomNav() {
  const pathname = usePathname();
  const active = activeKeyFor(pathname);

  return (
    <nav
      className="md:hidden fixed bottom-0 inset-x-0 bg-navy-950/95 backdrop-blur-xl border-t border-navy-800 z-50 safe-area-pb"
      aria-label="Main navigation"
      data-testid="bottom-nav"
    >
      <ul className="flex justify-around items-stretch px-1">
        {TABS.map((tab) => {
          const Icon = tab.icon;
          const isActive = active === tab.key;
          return (
            <li key={tab.key} className="flex-1">
              <Link
                href={tab.href}
                aria-current={isActive ? "page" : undefined}
                className={`flex flex-col items-center justify-center gap-1 py-2.5 px-1 text-[11px] font-medium transition-colors min-h-[56px] ${
                  isActive
                    ? "text-cyan-400 border-t-2 border-cyan-500 bg-cyan-500/5"
                    : "text-navy-400 hover:text-navy-200 border-t-2 border-transparent"
                }`}
              >
                <Icon className="w-5 h-5 shrink-0" aria-hidden="true" />
                <span className="max-w-full break-words leading-tight text-center">
                  {tab.label}
                </span>
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
