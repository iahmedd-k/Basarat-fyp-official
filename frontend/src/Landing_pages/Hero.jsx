import React from "react";
import {
  Search,
  TrendingUp,
  Filter,
  ArrowUpDown,
  Zap,
  Activity,
  Briefcase,
  LogIn,
  Rocket,
  ArrowRight,
} from "lucide-react";

/**
 * Ticker Analysts — landing page recreation
 * Tailwind CSS only (core utility classes), lucide-react icons.
 * Designed to fill 100% of the viewport height (100vh) on a standard
 * desktop screen, matching the reference screenshot 1:1 in layout,
 * type scale, spacing and color.
 *
 * IMPORTANT — font: the reference uses Inter. This component loads it
 * via a <link> tag and pins font-family explicitly, so it renders the
 * same regardless of your project's default Tailwind font stack. If
 * your app already loads Inter globally, you can delete the two
 * <link> tags below and just keep the fontFamily style (or your own
 * Tailwind `font-sans` config pointing at Inter).
 */

const TRY_TICKERS = [
  { symbol: "EFERT", emoji: "🌱", bg: "bg-emerald-100" },
  { symbol: "LUCK", emoji: "🌺", bg: "bg-rose-100" },
  { symbol: "HBL", emoji: "HBL", bg: "bg-emerald-800 text-white text-[9px] font-bold" },
  { symbol: "SYS", emoji: "S", bg: "bg-gray-100 text-gray-700 font-bold" },
  { symbol: "OGDC", emoji: "🌐", bg: "bg-blue-100" },
];

const LOGO_ROW = [
  { symbol: "EFERT", emoji: "🌱", bg: "bg-emerald-100" },
  { symbol: "LUCK", emoji: "🌺", bg: "bg-rose-100" },
  { symbol: "HBL", emoji: "HBL", bg: "bg-emerald-800 text-white text-[8px] font-bold" },
  { symbol: "OGDC", emoji: "🌐", bg: "bg-blue-100" },
  { symbol: "SYS", emoji: "S", bg: "bg-gray-100 text-gray-700 font-bold" },
  { symbol: "PSO", emoji: "🛢️", bg: "bg-orange-100" },
  { symbol: "MARI", emoji: "🔶", bg: "bg-amber-100" },
  { symbol: "MCB", emoji: "🏦", bg: "bg-gray-200" },
];

const STATS = [
  { value: "10K+", label: "investors" },
  { value: "500+", label: "stocks" },
  { value: "40+", label: "filters" },
  { value: "14", label: "advanced screens" },
];

const NAV_ITEMS = [
  { label: "Screener", icon: Filter },
  { label: "Compare", icon: ArrowUpDown },
  { label: "Advanced Screens", icon: Zap },
  { label: "Activities", icon: Activity },
  { label: "2026 Broker Picks", icon: TrendingUp },
  { label: "Portfolio", icon: Briefcase },
];

function KbdBadge({ className = "" }) {
  return (
    <span
      className={`flex h-6 w-6 items-center justify-center rounded-md border border-gray-200 bg-white text-[11px] font-medium text-gray-400 ${className}`}
    >
      ⌘K
    </span>
  );
}

export default function TickerAnalystsLanding() {
  return (
    <>
      <link rel="preconnect" href="https://fonts.googleapis.com" />
      <link
        href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap"
        rel="stylesheet"
      />
      <div
        className="flex h-screen w-full flex-col overflow-hidden bg-white"
        style={{
          fontFamily:
            "'Inter', ui-sans-serif, system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif",
        }}
      >
        {/* Header */}
        <header className="flex shrink-0 items-center justify-between gap-4 border-b border-gray-100 px-8 py-3.5">
          {/* Logo */}
          <div className="flex shrink-0 items-center gap-2">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-emerald-400">
              <TrendingUp className="h-5 w-5 text-white" strokeWidth={2.5} />
            </div>
            <span className="whitespace-nowrap text-lg font-bold text-gray-900">
              ticker analysts
            </span>
          </div>

          {/* Search */}
          <div className="flex w-full max-w-xs shrink items-center gap-2 rounded-lg bg-gray-50 px-3 py-2">
            <Search className="h-4 w-4 shrink-0 text-gray-400" />
            <span className="flex-1 truncate text-sm text-gray-400">
              Search companies...
            </span>
            <KbdBadge className="border-gray-200 bg-gray-100" />
          </div>

          {/* Nav */}
          <nav className="flex shrink-0 items-center gap-5 xl:gap-6">
            {NAV_ITEMS.map(({ label, icon: Icon }) => (
              <a
                key={label}
                href="#"
                className="flex items-center gap-1.5 whitespace-nowrap text-sm font-medium text-gray-600 hover:text-gray-900"
              >
                <Icon className="h-4 w-4" />
                {label}
              </a>
            ))}
          </nav>

          {/* Login */}
          <button className="flex shrink-0 items-center gap-2 rounded-full bg-black px-5 py-2.5 text-sm font-medium text-white hover:bg-gray-800">
            <LogIn className="h-4 w-4" />
            Login
          </button>
        </header>

      {/* Hero */}
      <main
        className="flex flex-1 flex-col items-center overflow-y-auto"
        style={{
          background:
            "radial-gradient(ellipse 80% 60% at 50% 0%, rgba(110,231,183,0.35) 0%, rgba(110,231,183,0.12) 45%, rgba(255,255,255,0) 75%)",
        }}
      >
        <div className="flex w-full flex-1 flex-col items-center justify-center px-4 pt-10">
          {/* Headline */}
          <h1 className="text-center text-6xl font-extrabold leading-[1.08] tracking-tight text-gray-900">
            Find stocks
            <br />
            <span className="relative inline-block text-emerald-500">
              worth investing in
              <svg
                viewBox="0 0 460 20"
                className="absolute -bottom-2 left-0 h-4 w-full text-emerald-300"
                preserveAspectRatio="none"
              >
                <path
                  d="M2 12 Q 60 2, 115 12 T 230 12 T 345 12 T 458 12"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="4"
                  strokeLinecap="round"
                />
              </svg>
            </span>
          </h1>

          {/* Subtext */}
          <p className="mt-7 max-w-xl text-center text-lg leading-relaxed text-gray-500">
            Research every company on the Pakistan Stock Exchange —
            <br />
            financials, insider activity, broker targets, and more.
          </p>

          {/* Search bar */}
          <div className="mt-9 flex w-full max-w-2xl items-center gap-3 rounded-2xl border border-gray-100 bg-white px-6 py-4 shadow-[0_8px_30px_rgba(0,0,0,0.06)]">
            <Search className="h-5 w-5 shrink-0 text-gray-400" />
            <span className="flex-1 text-base text-gray-400">Search for a company</span>
            <KbdBadge />
          </div>

          {/* Try tickers */}
          <div className="mt-5 flex flex-wrap items-center justify-center gap-2.5">
            <span className="text-sm text-gray-500">Try:</span>
            {TRY_TICKERS.map((t) => (
              <button
                key={t.symbol}
                className="flex items-center gap-2 rounded-full border border-gray-200 bg-white px-3.5 py-1.5 text-sm font-medium text-gray-700 hover:border-gray-300"
              >
                <span
                  className={`flex h-4 w-4 items-center justify-center rounded-full text-[9px] leading-none ${t.bg}`}
                >
                  {t.emoji}
                </span>
                {t.symbol}
              </button>
            ))}
          </div>

          {/* CTA */}
          <button className="mt-7 flex items-center gap-2 rounded-full border-2 border-emerald-200 px-6 py-3 text-[15px] font-semibold text-emerald-600 hover:bg-emerald-50">
            <Rocket className="h-4 w-4" />
            Invest with Nafa
            <ArrowRight className="h-4 w-4" />
          </button>
        </div>

        {/* Stats */}
        <div className="mt-10 flex w-full shrink-0 items-center justify-center gap-8 border-t border-gray-100 py-6 text-sm">
          {STATS.map((s, i) => (
            <React.Fragment key={s.label}>
              {i > 0 && <span className="h-4 w-px bg-gray-200" />}
              <span className="text-gray-600">
                <span className="font-bold text-gray-900">{s.value}</span> {s.label}
              </span>
            </React.Fragment>
          ))}
        </div>

        {/* Logo row */}
        <div className="flex w-full shrink-0 flex-wrap items-center justify-center gap-8 border-t border-gray-100 py-5 opacity-70">
          {LOGO_ROW.map((t) => (
            <div key={t.symbol} className="flex items-center gap-2">
              <span
                className={`flex h-5 w-5 items-center justify-center rounded-full text-[8px] leading-none ${t.bg}`}
              >
                {t.emoji}
              </span>
              <span className="text-sm font-medium text-gray-600">{t.symbol}</span>
            </div>
          ))}
        </div>
      </main>
      </div>
    </>
  );
}