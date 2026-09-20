import React, { useMemo, useState } from "react";
import { LineChart, Line, ResponsiveContainer } from "recharts";
import {
  Search,
  TrendingUp,
  TrendingDown,
  Activity,
  ArrowRight,
  ArrowLeft,
  List,
} from "lucide-react";

/**
 * Market Pulse + All Stocks browser + stock-detail placeholder.
 * Single self-contained component, internal view-state router
 * (no react-router needed): "pulse" -> "browse" -> "detail".
 *
 * Charts are real <LineChart> sparklines (recharts) driven by
 * deterministic dummy random-walk data, not static images.
 * All filtering (search box, index chips, gainers/losers/most-active
 * tabs) is functional against the dummy dataset below.
 */

/* ---------------------------------- utils --------------------------------- */

// Deterministic PRNG so sparklines don't reshuffle on every re-render.
function mulberry32(seed) {
  return function () {
    seed |= 0;
    seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function buildSparkline(seed, points = 18, bias = 0.6) {
  const rand = mulberry32(seed);
  let v = 50;
  const data = [];
  for (let i = 0; i < points; i++) {
    v += (rand() - (1 - bias)) * 6;
    data.push({ i, v: Math.round(v * 100) / 100 });
  }
  return data;
}

/* --------------------------------- dummy data ------------------------------- */

const INDEXES = [
  {
    name: "KSE 100",
    value: "170,884.58",
    change: "1,841.38",
    changePercent: "1.09",
    positive: true,
    spark: buildSparkline(1),
  },
  {
    name: "KSE 30",
    value: "50,882.99",
    change: "585.21",
    changePercent: "1.16",
    positive: true,
    spark: buildSparkline(2),
  },
  {
    name: "KMI 30",
    value: "243,139.24",
    change: "2,522.68",
    changePercent: "1.05",
    positive: true,
    spark: buildSparkline(3),
  },
  {
    name: "ALLSHR",
    value: "103,297.22",
    change: "1,052.6",
    changePercent: "1.03",
    positive: true,
    spark: buildSparkline(4),
  },
];

const AVATAR = (bg, text, textColor = "text-white") =>
  `flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-[11px] font-bold ${bg} ${textColor}`;

const GAINERS = [
  { symbol: "LSEFSL", name: "LSE Financial Services Limited.", price: "3.76", changePercent: "19.75", positive: true, avatarBg: "bg-emerald-100", avatarText: "text-emerald-700", initials: "LS" },
  { symbol: "MDTL", name: "Media Times Limited", price: "8.6", changePercent: "13.16", positive: true, avatarBg: "bg-emerald-100", avatarText: "text-emerald-700", initials: "▲" },
  { symbol: "FCSC", name: "First Capital Securities Corporation", price: "5.59", changePercent: "12.70", positive: true, avatarBg: "bg-emerald-100", avatarText: "text-emerald-700", initials: "▲" },
  { symbol: "CHBL", name: "Chenab Limited", price: "10.69", changePercent: "10.32", positive: true, avatarBg: "bg-amber-100", avatarText: "text-amber-700", initials: "CH" },
  { symbol: "JATM", name: "J.A. Textile Mills Limited", price: "12.45", changePercent: "10.01", positive: true, avatarBg: "bg-sky-100", avatarText: "text-sky-700", initials: "JA" },
  { symbol: "TSBL", name: "Treet Battery Limited", price: "6.21", changePercent: "9.44", positive: true, avatarBg: "bg-violet-100", avatarText: "text-violet-700", initials: "TB" },
];

const LOSERS = [
  { symbol: "PKGP", name: "Pak General Insurance Company", price: "4.02", changePercent: "8.91", positive: false, avatarBg: "bg-rose-100", avatarText: "text-rose-700", initials: "PG" },
  { symbol: "SITC", name: "Sind Textile Mills Limited", price: "7.15", changePercent: "7.60", positive: false, avatarBg: "bg-rose-100", avatarText: "text-rose-700", initials: "ST" },
  { symbol: "AWTL", name: "AWT Investments Limited", price: "9.88", changePercent: "6.24", positive: false, avatarBg: "bg-rose-100", avatarText: "text-rose-700", initials: "AW" },
  { symbol: "GATI", name: "Gatron Industries Limited", price: "34.10", changePercent: "5.02", positive: false, avatarBg: "bg-rose-100", avatarText: "text-rose-700", initials: "GI" },
  { symbol: "HIRAT", name: "Hira Textile Mills", price: "2.94", changePercent: "4.75", positive: false, avatarBg: "bg-rose-100", avatarText: "text-rose-700", initials: "HT" },
];

const MOST_ACTIVE = [
  { symbol: "PIBTL", name: "Pakistan International Bulk Terminal", price: "9.34", changePercent: "2.15", positive: true, avatarBg: "bg-blue-100", avatarText: "text-blue-700", initials: "PB" },
  { symbol: "WTL", name: "WorldCall Telecom Limited", price: "1.42", changePercent: "1.43", positive: true, avatarBg: "bg-indigo-100", avatarText: "text-indigo-700", initials: "WT" },
  { symbol: "KEL", name: "K-Electric Limited", price: "5.10", changePercent: "0.79", positive: true, avatarBg: "bg-yellow-100", avatarText: "text-yellow-700", initials: "KE" },
  { symbol: "BOP", name: "The Bank of Punjab", price: "12.88", changePercent: "1.02", positive: false, avatarBg: "bg-teal-100", avatarText: "text-teal-700", initials: "BP" },
  { symbol: "FFL", name: "Fauji Foods Limited", price: "17.63", changePercent: "3.30", positive: false, avatarBg: "bg-lime-100", avatarText: "text-lime-700", initials: "FF" },
];

const PULSE_TABS = {
  gainers: { label: "Gainers", icon: TrendingUp, data: GAINERS },
  losers: { label: "Losers", icon: TrendingDown, data: LOSERS },
  active: { label: "Most Active", icon: Activity, data: MOST_ACTIVE },
};

// Full browsable universe (All stocks screen). "indices" tags which
// index chip(s) each row belongs to, used by the chip filter below.
const ALL_STOCKS = [
  { symbol: "786", name: "786 Investments Limited", sector: "INV. BANKS / INV. COS. / SECURITIES COS.", price: "22.22", changePercent: "5.56", positive: true, volume: "95.8K", shariah: false, indices: ["ALLSHR"], avatarBg: "bg-emerald-900", avatarText: "text-emerald-300", initials: "7" },
  { symbol: "AABS", name: "Al-Abbas Sugar Mills Limited", sector: "SUGAR & ALLIED INDUSTRIES", price: "793.27", changePercent: "0.52", positive: false, volume: "74", shariah: false, indices: ["ALLSHR"], avatarBg: "bg-indigo-100", avatarText: "text-indigo-700", initials: "▲" },
  { symbol: "AATM", name: "Ali Asghar Textile Mills Limited", sector: "TEXTILE SPINNING", price: "45.39", changePercent: "0.91", positive: true, volume: "18.1K", shariah: false, indices: ["ALLSHR"], avatarBg: "bg-sky-100", avatarText: "text-sky-700", initials: "AT" },
  { symbol: "ABL", name: "Allied Bank Limited", sector: "COMMERCIAL BANKS", price: "170.35", changePercent: "0.09", positive: true, volume: "22.2K", shariah: false, indices: ["KSE100", "KSE30", "ALLSHR"], avatarBg: "bg-red-100", avatarText: "text-red-700", initials: "AB" },
  { symbol: "ABOT", name: "Abbott Laboratories (Pakistan) Limited", sector: "PHARMACEUTICALS", price: "923.72", changePercent: "0.91", positive: true, volume: "2.1K", shariah: true, indices: ["KSE100", "KMI30", "ALLSHR"], avatarBg: "bg-blue-500", avatarText: "text-white", initials: "AB" },
  { symbol: "ACIETF", name: "Alfalah Consumer Index (ETF)", sector: "EXCHANGE TRADED FUNDS", price: "16.57", changePercent: "1.66", positive: true, volume: "1.5K", shariah: false, indices: ["ALLSHR"], avatarBg: "bg-gray-200", avatarText: "text-gray-700", initials: "AC" },
  { symbol: "ACPL", name: "Attock Cement Pakistan Limited", sector: "CEMENT", price: "230.00", changePercent: "0.00", positive: true, volume: "12.9K", shariah: true, indices: ["KSE100", "KMI30", "ALLSHR"], avatarBg: "bg-gray-800", avatarText: "text-white", initials: "AC" },
  { symbol: "ADAMS", name: "Adam Sugar Mills Limited", sector: "SUGAR & ALLIED INDUSTRIES", price: "38.10", changePercent: "1.24", positive: false, volume: "3.4K", shariah: true, indices: ["ALLSHR"], avatarBg: "bg-orange-100", avatarText: "text-orange-700", initials: "AS" },
  { symbol: "AGP", name: "AGP Limited", sector: "PHARMACEUTICALS", price: "112.60", changePercent: "2.03", positive: true, volume: "6.7K", shariah: true, indices: ["KMI30", "ALLSHR"], avatarBg: "bg-teal-100", avatarText: "text-teal-700", initials: "AG" },
  { symbol: "AICL", name: "Adamjee Insurance Company Limited", sector: "INSURANCE", price: "64.85", changePercent: "0.77", positive: true, volume: "9.9K", shariah: false, indices: ["KSE100", "ALLSHR"], avatarBg: "bg-violet-100", avatarText: "text-violet-700", initials: "AI" },
  { symbol: "APL", name: "Attock Petroleum Limited", sector: "OIL & GAS MARKETING", price: "486.02", changePercent: "1.88", positive: true, volume: "4.2K", shariah: true, indices: ["KSE100", "KMI30", "ALLSHR"], avatarBg: "bg-amber-100", avatarText: "text-amber-700", initials: "AP" },
  { symbol: "BAFL", name: "Bank Alfalah Limited", sector: "COMMERCIAL BANKS", price: "89.40", changePercent: "0.34", positive: false, volume: "31.5K", shariah: false, indices: ["KSE100", "KSE30", "ALLSHR"], avatarBg: "bg-red-600", avatarText: "text-white", initials: "BA" },
  { symbol: "DGKC", name: "D.G. Khan Cement Company Limited", sector: "CEMENT", price: "142.75", changePercent: "1.45", positive: true, volume: "27.8K", shariah: true, indices: ["KSE100", "KMI30", "ALLSHR"], avatarBg: "bg-stone-200", avatarText: "text-stone-700", initials: "DG" },
  { symbol: "ENGRO", name: "Engro Corporation Limited", sector: "FERTILIZER", price: "312.90", changePercent: "0.61", positive: true, volume: "15.6K", shariah: true, indices: ["KSE100", "KSE30", "KMI30", "ALLSHR"], avatarBg: "bg-emerald-600", avatarText: "text-white", initials: "EN" },
  { symbol: "FFC", name: "Fauji Fertilizer Company Limited", sector: "FERTILIZER", price: "128.33", changePercent: "0.98", positive: false, volume: "19.3K", shariah: true, indices: ["KSE100", "KSE30", "KMI30", "ALLSHR"], avatarBg: "bg-lime-100", avatarText: "text-lime-700", initials: "FF" },
  { symbol: "HBL", name: "Habib Bank Limited", sector: "COMMERCIAL BANKS", price: "142.18", changePercent: "0.42", positive: true, volume: "24.7K", shariah: false, indices: ["KSE100", "KSE30", "ALLSHR"], avatarBg: "bg-emerald-800", avatarText: "text-white", initials: "HB" },
  { symbol: "LUCK", name: "Lucky Cement Limited", sector: "CEMENT", price: "1,120.50", changePercent: "1.12", positive: true, volume: "8.9K", shariah: true, indices: ["KSE100", "KSE30", "KMI30", "ALLSHR"], avatarBg: "bg-rose-100", avatarText: "text-rose-700", initials: "LC" },
  { symbol: "MARI", name: "Mari Petroleum Company Limited", sector: "OIL & GAS EXPLORATION", price: "2,845.00", changePercent: "0.55", positive: false, volume: "3.1K", shariah: true, indices: ["KSE100", "KSE30", "KMI30", "ALLSHR"], avatarBg: "bg-amber-200", avatarText: "text-amber-800", initials: "MA" },
  { symbol: "MCB", name: "MCB Bank Limited", sector: "COMMERCIAL BANKS", price: "268.40", changePercent: "0.21", positive: true, volume: "11.4K", shariah: false, indices: ["KSE100", "KSE30", "ALLSHR"], avatarBg: "bg-gray-300", avatarText: "text-gray-700", initials: "MC" },
  { symbol: "OGDC", name: "Oil & Gas Development Company Limited", sector: "OIL & GAS EXPLORATION", price: "158.95", changePercent: "1.30", positive: true, volume: "42.6K", shariah: true, indices: ["KSE100", "KSE30", "KMI30", "ALLSHR"], avatarBg: "bg-blue-100", avatarText: "text-blue-700", initials: "OG" },
  { symbol: "PSO", name: "Pakistan State Oil Company Limited", sector: "OIL & GAS MARKETING", price: "234.10", changePercent: "2.44", positive: true, volume: "18.0K", shariah: false, indices: ["KSE100", "KSE30", "ALLSHR"], avatarBg: "bg-orange-100", avatarText: "text-orange-700", initials: "PS" },
  { symbol: "SYS", name: "Systems Limited", sector: "TECHNOLOGY & COMMUNICATION", price: "612.75", changePercent: "3.02", positive: true, volume: "6.3K", shariah: false, indices: ["KSE100", "KSE30", "ALLSHR"], avatarBg: "bg-gray-100", avatarText: "text-gray-700", initials: "S" },
  { symbol: "UBL", name: "United Bank Limited", sector: "COMMERCIAL BANKS", price: "298.60", changePercent: "0.15", positive: false, volume: "13.2K", shariah: false, indices: ["KSE100", "KSE30", "ALLSHR"], avatarBg: "bg-blue-800", avatarText: "text-white", initials: "UB" },
];

const INDEX_CHIPS = ["All", "KSE100", "KSE30", "KMI30", "ALLSHR"];
const INDEX_CHIP_LABEL = { All: "All", KSE100: "KSE 100", KSE30: "KSE 30", KMI30: "KMI 30", ALLSHR: "ALLSHR" };

const BROWSE_TABS = [
  { key: "all", label: "All stocks", icon: List },
  { key: "gainers", label: "Top gainers", icon: TrendingUp },
  { key: "losers", label: "Top losers", icon: TrendingDown },
  { key: "active", label: "Most active", icon: Activity },
];

/* --------------------------------- small bits ------------------------------- */

function Sparkline({ data, positive }) {
  return (
    <div className="h-10 w-28">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data}>
          <Line
            type="monotone"
            dataKey="v"
            stroke={positive ? "#10b981" : "#ef4444"}
            strokeWidth={2}
            dot={false}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

function ChangeText({ positive, children, className = "" }) {
  return (
    <span
      className={`inline-flex items-center gap-0.5 text-sm font-semibold ${
        positive ? "text-emerald-600" : "text-red-500"
      } ${className}`}
    >
      {positive ? "▲" : "▼"} {children}
    </span>
  );
}

function ChangePill({ positive, children }) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-semibold ${
        positive ? "bg-emerald-50 text-emerald-600" : "bg-red-50 text-red-600"
      }`}
    >
      {positive ? "▲" : "▼"} {children}%
    </span>
  );
}

/* --------------------------------- Market Pulse ------------------------------ */

function MarketPulseView({ onBrowseAll, onSelectStock }) {
  const [tab, setTab] = useState("gainers");
  const active = PULSE_TABS[tab];

  return (
    <div className="mx-auto max-w-5xl px-6 py-10">
      {/* Heading */}
      <h1 className="text-3xl font-bold text-gray-900">Market pulse</h1>
      <div className="mt-2 flex items-center gap-4 text-sm text-gray-500">
        <span className="flex items-center gap-1.5">
          <span className="h-2 w-2 rounded-full bg-emerald-500" />
          339 advancing
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-2 w-2 rounded-full bg-red-500" />
          111 declining
        </span>
        <span>Vol 574.8M</span>
      </div>

      {/* Index grid */}
      <div className="mt-6 grid grid-cols-1 overflow-hidden rounded-2xl border border-gray-100 sm:grid-cols-2">
        {INDEXES.map((idx, i) => (
          <div
            key={idx.name}
            className={`flex items-center justify-between gap-4 px-6 py-5 ${
              i % 2 === 0 ? "sm:border-r sm:border-gray-100" : ""
            } ${i < 2 ? "border-b border-gray-100" : ""}`}
          >
            <span className="text-sm font-semibold text-gray-900">{idx.name}</span>
            <Sparkline data={idx.spark} positive={idx.positive} />
            <div className="text-right">
              <div className="text-base font-bold text-gray-900">{idx.value}</div>
              <ChangeText positive={idx.positive}>
                {idx.change} (+{idx.changePercent}%)
              </ChangeText>
            </div>
          </div>
        ))}
      </div>

      {/* Today's stocks */}
      <div className="mt-6 rounded-2xl border border-gray-100">
        <div className="flex items-center justify-between px-6 pt-5">
          <h2 className="text-lg font-bold text-gray-900">Today's stocks</h2>
          <button
            onClick={onBrowseAll}
            className="flex items-center gap-1 text-sm text-gray-500 hover:text-gray-900"
          >
            Browse all stocks
            <ArrowRight className="h-3.5 w-3.5" />
          </button>
        </div>

        <div className="flex items-center gap-2 px-6 pb-5 pt-4">
          {Object.entries(PULSE_TABS).map(([key, t]) => {
            const isActive = key === tab;
            const Icon = t.icon;
            return (
              <button
                key={key}
                onClick={() => setTab(key)}
                className={`flex items-center gap-1.5 rounded-full px-4 py-2 text-sm font-semibold transition ${
                  isActive
                    ? "bg-emerald-500 text-white"
                    : "border border-gray-200 text-gray-600 hover:border-gray-300"
                }`}
              >
                <Icon className="h-3.5 w-3.5" />
                {t.label}
              </button>
            );
          })}
        </div>

        <div
          className="grid gap-4 border-t border-gray-100 px-6 py-2.5 text-xs font-medium tracking-wide text-gray-400"
          style={{ gridTemplateColumns: "1fr 100px 120px" }}
        >
          <span>STOCKS</span>
          <span className="text-right">PRICE</span>
          <span className="text-right">CHANGE</span>
        </div>

        <div>
          {active.data.map((s) => (
            <button
              key={s.symbol}
              onClick={() => onSelectStock(s)}
              className="grid w-full items-center gap-4 border-t border-gray-50 px-6 py-4 text-left hover:bg-gray-50"
              style={{ gridTemplateColumns: "1fr 100px 120px" }}
            >
              <span className="flex items-center gap-3">
                <span className={AVATAR(s.avatarBg, s.avatarText)}>{s.initials}</span>
                <span>
                  <span className="block text-sm font-semibold text-gray-900">{s.name}</span>
                  <span className="block text-xs text-gray-400">{s.symbol}</span>
                </span>
              </span>
              <span className="text-right text-sm text-gray-900">{s.price}</span>
              <span className="text-right">
                <ChangeText positive={s.positive}>{s.changePercent}%</ChangeText>
              </span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

/* --------------------------------- All Stocks -------------------------------- */

function AllStocksView({ onSelectStock }) {
  const [tab, setTab] = useState("all");
  const [chip, setChip] = useState("All");
  const [search, setSearch] = useState("");

  const rows = useMemo(() => {
    let list = ALL_STOCKS.filter(
      (s) =>
        s.symbol.toLowerCase().includes(search.toLowerCase()) ||
        s.name.toLowerCase().includes(search.toLowerCase())
    );
    if (chip !== "All") list = list.filter((s) => s.indices.includes(chip));

    if (tab === "gainers") {
      list = list.filter((s) => s.positive).sort((a, b) => b.changePercent - a.changePercent);
    } else if (tab === "losers") {
      list = list.filter((s) => !s.positive).sort((a, b) => b.changePercent - a.changePercent);
    } else if (tab === "active") {
      list = [...list].sort(
        (a, b) => parseFloat(b.volume) - parseFloat(a.volume)
      );
    }
    return list;
  }, [tab, chip, search]);

  const upCount = ALL_STOCKS.filter((s) => s.positive).length;
  const downCount = ALL_STOCKS.length - upCount;

  return (
    <div className="mx-auto max-w-5xl px-6 py-8">
      {/* Top tabs + search */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-6">
          {BROWSE_TABS.map(({ key, label, icon: Icon }) => {
            const isActive = key === tab;
            return (
              <button
                key={key}
                onClick={() => setTab(key)}
                className={
                  isActive
                    ? "flex items-center gap-2 rounded-full bg-black px-4 py-2 text-sm font-medium text-white"
                    : "flex items-center gap-1.5 text-sm font-medium text-gray-600 hover:text-gray-900"
                }
              >
                <Icon className="h-4 w-4" />
                {label}
              </button>
            );
          })}
        </div>

        <div className="flex w-72 items-center gap-2 rounded-full border border-gray-200 px-4 py-2">
          <Search className="h-4 w-4 shrink-0 text-gray-400" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search symbol or name"
            className="w-full bg-transparent text-sm text-gray-700 outline-none placeholder:text-gray-400"
          />
        </div>
      </div>

      {/* Index chips */}
      <div className="mt-5 flex items-center gap-6 border-b border-gray-100 pb-3 text-sm">
        {INDEX_CHIPS.map((c) => (
          <button
            key={c}
            onClick={() => setChip(c)}
            className={
              chip === c
                ? "font-semibold text-emerald-600"
                : "font-medium text-gray-400 hover:text-gray-600"
            }
          >
            {INDEX_CHIP_LABEL[c]}
          </button>
        ))}
      </div>

      {/* Stats */}
      <div className="mt-4 flex items-center gap-2 text-sm text-gray-500">
        <span className="font-semibold text-gray-900">{ALL_STOCKS.length}</span> companies
        <span className="text-gray-300">·</span>
        <span className="font-medium text-emerald-600">{upCount} up</span>
        <span className="text-gray-300">/</span>
        <span className="font-medium text-red-500">{downCount} down</span>
      </div>

      {/* Table */}
      <div
        className="mt-4 grid gap-4 border-b border-gray-100 px-2 py-3 text-xs font-medium tracking-wide text-gray-400"
        style={{ gridTemplateColumns: "1fr 120px 140px 100px" }}
      >
        <span>COMPANY</span>
        <span className="text-right">PRICE</span>
        <span className="text-right">CHANGE</span>
        <span className="text-right">VOLUME</span>
      </div>

      <div>
        {rows.map((s) => (
          <button
            key={s.symbol}
            onClick={() => onSelectStock(s)}
            className="grid w-full items-center gap-4 border-b border-gray-50 px-2 py-4 text-left hover:bg-gray-50"
            style={{ gridTemplateColumns: "1fr 120px 140px 100px" }}
          >
            <span className="flex items-center gap-3">
              <span className={AVATAR(s.avatarBg, s.avatarText)}>{s.initials}</span>
              <span>
                <span className="flex items-center gap-2">
                  <span className="text-sm font-semibold text-gray-900">{s.symbol}</span>
                  {s.shariah && (
                    <span className="rounded bg-emerald-50 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-emerald-600">
                      Shariah
                    </span>
                  )}
                </span>
                <span className="block text-xs text-gray-400">
                  {s.name} · <span className="tracking-wide">{s.sector}</span>
                </span>
              </span>
            </span>
            <span className="text-right text-sm font-semibold text-gray-900">{s.price}</span>
            <span className="flex justify-end">
              <ChangePill positive={s.positive}>{s.changePercent}</ChangePill>
            </span>
            <span className="text-right text-sm text-gray-500">{s.volume}</span>
          </button>
        ))}
        {rows.length === 0 && (
          <div className="py-12 text-center text-sm text-gray-400">
            No stocks match your search.
          </div>
        )}
      </div>
    </div>
  );
}

/* ------------------------------- Stock Detail (placeholder) ------------------------------ */

function StockDetailView({ stock, onBack }) {
  return (
    <div className="mx-auto max-w-3xl px-6 py-10">
      <button
        onClick={onBack}
        className="flex items-center gap-1.5 text-sm font-medium text-gray-500 hover:text-gray-900"
      >
        <ArrowLeft className="h-4 w-4" />
        Back
      </button>

      <div className="mt-6 flex items-center gap-4">
        <span className={`${AVATAR(stock.avatarBg, stock.avatarText)} h-12 w-12 text-sm`}>
          {stock.initials}
        </span>
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold text-gray-900">{stock.symbol}</h1>
            {stock.shariah && (
              <span className="rounded bg-emerald-50 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-emerald-600">
                Shariah
              </span>
            )}
          </div>
          <p className="text-sm text-gray-500">{stock.name}</p>
        </div>
      </div>

      <div className="mt-6 flex items-baseline gap-3">
        <span className="text-3xl font-bold text-gray-900">{stock.price}</span>
        <ChangeText positive={stock.positive} className="text-base">
          {stock.changePercent}%
        </ChangeText>
      </div>

      <div className="mt-8 flex h-64 items-center justify-center rounded-2xl border border-dashed border-gray-200 text-sm text-gray-400">
        Full stock detail page — price chart, financials, insider activity
        and broker targets will go here.
      </div>
    </div>
  );
}

/* --------------------------------------- App --------------------------------------- */

export default function MarketPulsePage() {
  const [view, setView] = useState("pulse"); // "pulse" | "browse" | "detail"
  const [previousView, setPreviousView] = useState("pulse");
  const [selectedStock, setSelectedStock] = useState(null);

  const openStock = (stock) => {
    setPreviousView(view);
    setSelectedStock(stock);
    setView("detail");
  };

  return (
    <div
      className="min-h-screen w-full bg-gray-50"
      style={{
        fontFamily:
          "'Inter', ui-sans-serif, system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif",
      }}
    >
      {view === "pulse" && (
        <MarketPulseView onBrowseAll={() => setView("browse")} onSelectStock={openStock} />
      )}
      {view === "browse" && (
        <div className="bg-white">
          <AllStocksView onSelectStock={openStock} />
        </div>
      )}
      {view === "detail" && selectedStock && (
        <div className="bg-white">
          <StockDetailView stock={selectedStock} onBack={() => setView(previousView)} />
        </div>
      )}
    </div>
  );
}