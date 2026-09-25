import React, { useEffect, useMemo, useState } from "react";
import { Activity, ArrowLeft, ArrowRight, List, Search, TrendingDown, TrendingUp } from "lucide-react";
import { requireApiBaseUrl } from "../api/config";

const INDEXES = [
  { code: "KSE100", label: "KSE 100" },
  { code: "KSE30", label: "KSE 30" },
  { code: "KMI30", label: "KMI 30" },
  { code: "ALLSHR", label: "ALLSHR" },
];
const INDEX_ENDPOINTS = { KSE100: "kse-100", KSE30: "kse-30", KMI30: "kmi-30" };
const TABS = [
  { key: "all", label: "All stocks", icon: List },
  { key: "gainers", label: "Top gainers", icon: TrendingUp },
  { key: "losers", label: "Top losers", icon: TrendingDown },
  { key: "active", label: "Most active", icon: Activity },
];

const hasNumber = (value) => value !== null && value !== undefined && value !== "" && Number.isFinite(Number(value));
const number = (value, digits = 2) =>
  hasNumber(value) ? Number(value).toLocaleString(undefined, { maximumFractionDigits: digits }) : "—";
const volume = (value) => hasNumber(value) ? Number(value).toLocaleString() : "—";
const quoteIsTraded = (stock) => Number(stock.volume) > 0 && Number(stock.current) > 0 && Number.isFinite(Number(stock.change_pct));

async function getJson(path) {
  const response = await fetch(`${requireApiBaseUrl()}${path}`, { headers: { Accept: "application/json" } });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body?.detail || body?.error?.message || `Market API returned ${response.status}`);
  return body;
}

function Freshness({ data }) {
  if (!data) return null;
  const label = data.as_of && Number.isFinite(Date.parse(data.as_of)) ? `As of ${new Date(data.as_of).toLocaleString()}` : "Update time unavailable";
  return <span className={`text-xs ${data.is_stale ? "text-amber-700" : "text-gray-500"}`}>
    {data.is_stale ? "Stale snapshot · " : "Live snapshot · "}{label}
  </span>;
}

function Change({ value, suffix = "%" }) {
  if (!hasNumber(value)) return <span className="text-gray-400">—</span>;
  const positive = Number(value) >= 0;
  return <span className={positive ? "font-semibold text-emerald-600" : "font-semibold text-red-500"}>
    {positive ? "▲" : "▼"} {number(Math.abs(Number(value)))}{suffix}
  </span>;
}

function MarketPulseView({ quotes, indices, sentiment, freshness, indexFreshness, loading, error, reload, onBrowseAll, onSelectStock }) {
  const [tab, setTab] = useState("gainers");
  const movers = useMemo(() => {
    const traded = quotes.filter(quoteIsTraded);
    if (tab === "gainers") return [...traded].sort((a, b) => Number(b.change_pct) - Number(a.change_pct)).slice(0, 6);
    if (tab === "losers") return [...traded].sort((a, b) => Number(a.change_pct) - Number(b.change_pct)).slice(0, 6);
    return [...quotes].filter((row) => Number(row.volume) > 0).sort((a, b) => Number(b.volume) - Number(a.volume)).slice(0, 6);
  }, [quotes, tab]);

  return <main className="mx-auto max-w-5xl px-6 py-10">
    <div className="flex flex-wrap items-end justify-between gap-3">
      <div><h1 className="text-3xl font-bold text-gray-900">Market pulse</h1><Freshness data={freshness} /></div>
      <button onClick={reload} className="rounded-full border px-4 py-2 text-sm">Refresh</button>
    </div>
    {error && <div role="alert" className="mt-5 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">{error}</div>}
    {sentiment && <div className="mt-5 flex flex-wrap gap-5 text-sm text-gray-600">
      <span><b className="text-emerald-600">{sentiment.advancing}</b> advancing</span>
      <span><b className="text-red-500">{sentiment.declining}</b> declining</span>
      <span>{sentiment.unchanged} unchanged</span>
      <span>{number(sentiment.gainers_pct)}% gaining</span>
    </div>}
    <section className="mt-6 grid grid-cols-1 overflow-hidden rounded-2xl border border-gray-100 bg-white sm:grid-cols-2">
      {indices.map((item, i) => <div key={item.code} className={`flex items-center justify-between gap-4 border-gray-100 px-6 py-5 ${i < 2 ? "border-b" : ""} ${i % 2 === 0 ? "sm:border-r" : ""}`}>
        <span className="text-sm font-semibold">{item.index}</span>
        <div className="text-right"><div className="font-bold">{number(item.current)}</div><div className="text-sm"><Change value={item.change} suffix="" /> <span className="text-gray-400">({number(item.change_pct)}%)</span></div></div>
      </div>)}
      {!indices.length && <div className="p-6 text-sm text-gray-500">{loading ? "Loading index data…" : "Index data is unavailable."}</div>}
    </section>
    <div className="mt-2"><Freshness data={indexFreshness} /></div>
    <section className="mt-6 rounded-2xl border border-gray-100 bg-white">
      <div className="flex items-center justify-between px-6 pt-5"><h2 className="text-lg font-bold">Market movers</h2><button onClick={onBrowseAll} className="flex items-center gap-1 text-sm text-gray-500">Browse stocks <ArrowRight size={15} /></button></div>
      <div className="flex gap-2 px-6 py-4">{["gainers", "losers", "active"].map((key) => <button key={key} onClick={() => setTab(key)} className={`rounded-full px-4 py-2 text-sm font-semibold ${tab === key ? "bg-emerald-500 text-white" : "border text-gray-600"}`}>{key === "active" ? "Most active" : key[0].toUpperCase() + key.slice(1)}</button>)}</div>
      {movers.map((stock) => <button key={stock.symbol} onClick={() => onSelectStock(stock)} className="grid w-full grid-cols-[1fr_100px_120px] items-center gap-3 border-t border-gray-50 px-6 py-4 text-left hover:bg-gray-50">
        <span><b className="block text-sm">{stock.name || stock.symbol}</b><small className="text-gray-400">{stock.symbol}</small></span>
        <span className="text-right text-sm">{number(stock.current)}</span><span className="text-right text-sm"><Change value={stock.change_pct} /></span>
      </button>)}
      {!movers.length && <div className="px-6 py-10 text-center text-sm text-gray-500">{loading ? "Loading market quotes…" : "No traded quote data is available."}</div>}
    </section>
  </main>;
}

function AllStocksView({ quotes, memberships, freshness, loading, onSelectStock }) {
  const [tab, setTab] = useState("all");
  const [chip, setChip] = useState("All");
  const [search, setSearch] = useState("");
  const rows = useMemo(() => {
    let list = quotes.filter((stock) => `${stock.symbol} ${stock.name || ""}`.toLowerCase().includes(search.toLowerCase()));
    if (chip !== "All") list = list.filter((stock) => memberships[chip]?.has(stock.symbol));
    if (tab === "gainers") list = list.filter(quoteIsTraded).sort((a, b) => Number(b.change_pct) - Number(a.change_pct));
    if (tab === "losers") list = list.filter(quoteIsTraded).sort((a, b) => Number(a.change_pct) - Number(b.change_pct));
    if (tab === "active") list = list.filter((stock) => Number(stock.volume) > 0).sort((a, b) => Number(b.volume) - Number(a.volume));
    return list;
  }, [quotes, memberships, tab, chip, search]);
  const traded = quotes.filter(quoteIsTraded);
  const advancing = traded.filter((stock) => Number(stock.change_pct) > 0).length;
  const declining = traded.filter((stock) => Number(stock.change_pct) < 0).length;

  return <main className="mx-auto max-w-5xl px-6 py-8">
    <div className="flex flex-wrap items-center justify-between gap-4"><div className="flex flex-wrap gap-3">{TABS.map(({ key, label, icon: Icon }) => <button key={key} onClick={() => setTab(key)} className={`flex items-center gap-2 rounded-full px-4 py-2 text-sm ${tab === key ? "bg-black text-white" : "text-gray-600"}`}><Icon size={16} />{label}</button>)}</div>
      <label className="flex w-72 items-center gap-2 rounded-full border px-4 py-2"><Search size={16} className="text-gray-400" /><input aria-label="Search stocks" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search symbol or name" className="w-full text-sm outline-none" /></label></div>
    <div className="mt-5 flex flex-wrap gap-5 border-b pb-3 text-sm">{["All", ...INDEXES.map((index) => index.code)].map((key) => <button key={key} onClick={() => setChip(key)} className={chip === key ? "font-semibold text-emerald-600" : "text-gray-500"}>{key === "All" ? "All" : INDEXES.find((i) => i.code === key)?.label}</button>)}</div>
    <div className="mt-4 flex flex-wrap items-center gap-3 text-sm text-gray-500"><span><b className="text-gray-900">{quotes.length}</b> quotes</span><span>·</span><span className="text-emerald-600">{advancing} up</span><span>/</span><span className="text-red-500">{declining} down</span><span className="ml-auto"><Freshness data={freshness} /></span></div>
    <div className="mt-4 grid grid-cols-[1fr_110px_120px_100px] gap-3 border-b px-2 py-3 text-xs font-medium text-gray-400"><span>COMPANY</span><span className="text-right">PRICE</span><span className="text-right">CHANGE</span><span className="text-right">VOLUME</span></div>
    {rows.map((stock) => <button key={stock.symbol} onClick={() => onSelectStock(stock)} className="grid w-full grid-cols-[1fr_110px_120px_100px] items-center gap-3 border-b px-2 py-4 text-left hover:bg-gray-50">
      <span><b className="block text-sm">{stock.symbol}</b><small className="text-gray-400">{stock.name || stock.symbol}{stock.sector ? ` · ${stock.sector}` : ""}</small>{memberships.KMI30?.has(stock.symbol) && <small className="ml-2 rounded bg-emerald-50 px-1.5 py-0.5 text-emerald-700">KMI-30</small>}</span>
      <span className="text-right text-sm">{number(stock.current)}</span><span className="text-right text-sm"><Change value={stock.change_pct} /></span><span className="text-right text-sm text-gray-500">{volume(stock.volume)}</span>
    </button>)}
    {!rows.length && <div className="py-12 text-center text-sm text-gray-500">{loading ? "Loading stock quotes…" : "No stocks match this filter or the data is unavailable."}</div>}
  </main>;
}

function StockDetailView({ stock, onBack, membership }) {
  return <main className="mx-auto max-w-3xl px-6 py-10">
    <button onClick={onBack} className="flex items-center gap-2 text-sm text-gray-500"><ArrowLeft size={16} />Back</button>
    <div className="mt-6"><h1 className="text-2xl font-bold">{stock.symbol}</h1><p className="text-gray-500">{stock.name || stock.symbol}</p>{membership && <span className="mt-2 inline-block rounded bg-emerald-50 px-2 py-1 text-xs text-emerald-700">KMI-30 member</span>}</div>
    <div className="mt-6 flex items-baseline gap-4"><span className="text-3xl font-bold">{number(stock.current)}</span><Change value={stock.change_pct} /></div>
    <dl className="mt-8 grid grid-cols-2 gap-4 rounded-2xl border p-5 text-sm"><dt className="text-gray-500">Previous close</dt><dd className="text-right">{number(stock.ldcp)}</dd><dt className="text-gray-500">Volume</dt><dd className="text-right">{volume(stock.volume)}</dd><dt className="text-gray-500">Day high</dt><dd className="text-right">{number(stock.high)}</dd><dt className="text-gray-500">Day low</dt><dd className="text-right">{number(stock.low)}</dd></dl>
    <p className="mt-5 text-sm text-gray-500">Historical chart and financial details are not shown here. This view displays only fields supplied by the market quote API.</p>
  </main>;
}

export default function MarketPulsePage() {
  const [view, setView] = useState("pulse");
  const [previousView, setPreviousView] = useState("pulse");
  const [selectedStock, setSelectedStock] = useState(null);
  const [quotes, setQuotes] = useState([]);
  const [indices, setIndices] = useState([]);
  const [indexFreshness, setIndexFreshness] = useState(null);
  const [sentiment, setSentiment] = useState(null);
  const [freshness, setFreshness] = useState(null);
  const [memberships, setMemberships] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function loadMarket() {
    try {
      const [quoteData] = await Promise.all([
        getJson("/market/quotes?limit=1000&sort_by=volume&order=desc"),
      ]);
      const optionalResults = await Promise.allSettled([
        getJson("/market/indices"),
        getJson("/market/sentiment-overview"),
        ...Object.entries(INDEX_ENDPOINTS).map(([, endpoint]) => getJson(`/market/indices/${endpoint}`)),
      ]);
      const indexResult = optionalResults[0];
      const indexData = indexResult.status === "fulfilled" ? indexResult.value : null;
      const rows = Array.isArray(quoteData.stocks) ? quoteData.stocks : [];
      setQuotes(rows);
      setIndices(Array.isArray(indexData?.indices) ? indexData.indices.filter((row) => INDEXES.some((index) => index.code === row.code)) : []);
      setIndexFreshness(indexData ? { as_of: indexData.as_of, is_stale: indexData.is_stale } : null);
      setSentiment(optionalResults[1].status === "fulfilled" ? optionalResults[1].value : null);
      setFreshness({ as_of: quoteData.as_of, is_stale: quoteData.is_stale });
      const codes = Object.keys(INDEX_ENDPOINTS);
      setMemberships(Object.fromEntries(codes.map((code, i) => {
        const result = optionalResults[i + 2];
        const members = result?.status === "fulfilled" && !result.value.is_stale ? result.value.constituents || [] : [];
        return [code, new Set(members.map((row) => row.symbol))];
      })));
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Market data could not be loaded.");
    } finally {
      setLoading(false);
    }
  }

  // Mount-time API synchronization populates state after its network request.
  // oxlint-disable-next-line react/set-state-in-effect
  useEffect(() => { void loadMarket(); }, []);
  const openStock = (stock) => { setPreviousView(view); setSelectedStock(stock); setView("detail"); };
  return <div className="min-h-screen w-full bg-gray-50" style={{ fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif" }}>
    {view === "pulse" && <MarketPulseView quotes={quotes} indices={indices} sentiment={sentiment} freshness={freshness} indexFreshness={indexFreshness} loading={loading} error={error} reload={() => { setLoading(true); void loadMarket(); }} onBrowseAll={() => setView("browse")} onSelectStock={openStock} />}
    {view === "browse" && <div className="bg-white"><AllStocksView quotes={quotes} memberships={memberships} freshness={freshness} loading={loading} onSelectStock={openStock} /></div>}
    {view === "detail" && selectedStock && <div className="bg-white"><StockDetailView stock={selectedStock} membership={memberships.KMI30?.has(selectedStock.symbol)} onBack={() => setView(previousView)} /></div>}
  </div>;
}
