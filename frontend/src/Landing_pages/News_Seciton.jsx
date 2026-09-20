import { useState, useMemo, useEffect, useRef, useCallback } from "react";
import {
  Search,
  Share2,
  ExternalLink,
  RefreshCw,
  Landmark,
  Newspaper,
  X,
  ArrowLeft,
} from "lucide-react";

/* ============================================================
   Config (matches the news module spec)
   ============================================================ */
const REFRESH_COOLDOWN_SEC = 300; // pull/refresh cooldown: 5 min
const AUTO_INTERVAL_MS = 30 * 60 * 1000; // background job: every 30 min
const PAGE_SIZE = 10;
const HOLIDAYS = ["2026-12-25"]; // maintained list, moon-sighting holidays get added late
const hm = (h, m) => h * 60 + m;
// Run windows in Asia/Karachi, keyed by weekday (1 = Mon). Open minus 15 min, to close.
const RUN_WINDOWS = {
  1: [[hm(9, 15), hm(15, 30)]],
  2: [[hm(9, 15), hm(15, 30)]],
  3: [[hm(9, 15), hm(15, 30)]],
  4: [[hm(9, 15), hm(15, 30)]],
  5: [[hm(9, 0), hm(16, 30)]], // Friday runs through the midday break
};

/* ============================================================
   Static lookups
   ============================================================ */
const SOURCES = {
  psx: { name: "PSX", type: "official", url: "https://dps.psx.com.pk/announcements/companies" },
  secp: { name: "SECP", type: "official", url: "https://www.secp.gov.pk" },
  sbp: { name: "SBP", type: "official", url: "https://www.sbp.org.pk" },
  ogra: { name: "OGRA", type: "official", url: "https://www.ogra.org.pk" },
  mof: { name: "Finance Ministry", type: "official", url: "https://www.finance.gov.pk" },
  br: { name: "Business Recorder", type: "news", url: "https://www.brecorder.com" },
  dawn: { name: "Dawn Business", type: "news", url: "https://www.dawn.com/business" },
  mettis: { name: "Mettis Global", type: "news", url: "https://mettisglobal.news" },
};

const UNIVERSE = {
  HBL: "Habib Bank Limited",
  UBL: "United Bank Limited",
  MEBL: "Meezan Bank Limited",
  OGDC: "Oil & Gas Development Company",
  PPL: "Pakistan Petroleum Limited",
  PSO: "Pakistan State Oil",
  LUCK: "Lucky Cement Limited",
  MLCF: "Maple Leaf Cement Factory",
  ENGRO: "Engro Corporation",
  FFC: "Fauji Fertilizer Company",
  HUBC: "The Hub Power Company",
  SYS: "Systems Limited",
};

const EVENT_LABEL = {
  results: "Results",
  dividend: "Dividend",
  board_meeting: "Board meeting",
  company_notice: "Company notice",
  regulatory: "Regulatory",
  policy_rate: "Policy rate",
  fuel_price: "Fuel price",
  budget_tax: "Budget and tax",
  other: "News",
};

const PORTFOLIO_CHIPS = [
  ["all", "All"],
  ["results", "Results"],
  ["dividend", "Dividends"],
  ["board_meeting", "Board meetings"],
  ["company_notice", "Company notices"],
];

const SENTIMENT = {
  bullish: { label: "Bullish", dot: "bg-emerald-500" },
  bearish: { label: "Bearish", dot: "bg-red-500" },
  neutral: { label: "Neutral", dot: "bg-slate-400" },
};

/* ============================================================
   Dummy data. Shape mirrors the API article object.
   Sentiment rules: FinBERT only for news sites, official = null (no dot).
   ============================================================ */
let _id = 1000;
const ago = (min) => new Date(Date.now() - min * 60000).toISOString();

function A(src, syms, event, title, summary, minsAgo, sent) {
  const s = SOURCES[src];
  return {
    id: ++_id,
    title,
    summary,
    source: { key: src, name: s.name, type: s.type },
    is_official: s.type === "official",
    published_at: ago(minsAgo),
    external_url: s.url,
    symbols: syms.map((x) => ({ symbol: x, name: UNIVERSE[x] })),
    event_type: event,
    sentiment: sent ? { label: sent[0], score: sent[1], method: "finbert" } : null,
  };
}

const SEED = [
  ["psx", ["MLCF"], "company_notice", "MLCF | Maple Leaf Cement Factory Limited Notice of Extraordinary General Meeting 19.10.2026", "Maple Leaf Cement has called an extraordinary general meeting for 19 October 2026. Shareholders can read the notice on PSX.", 40, null],
  ["br", ["LUCK", "MLCF"], "other", "Cement despatches rise in August on stronger local demand", "Local cement sales grew year on year while exports stayed weak, according to industry data.", 75, ["bullish", 0.87]],
  ["psx", ["HBL"], "board_meeting", "Board Meeting", "The HBL board will meet to consider the interim financial statements. Book closure dates, if any, will follow.", 120, null],
  ["sbp", [], "policy_rate", "SBP Monetary Policy Committee announces policy rate decision", "The State Bank has published its latest policy statement. Read the full statement on the SBP website.", 210, null],
  ["mettis", ["PSO"], "other", "PSO signs new fuel supply agreement", "Pakistan State Oil has signed a supply deal that could support volumes in the coming quarters.", 260, ["bullish", 0.81]],
  ["psx", ["OGDC"], "dividend", "Final cash dividend for the year ended June 30, 2026", "The OGDC board has recommended a final cash dividend. Book closure dates are in the notice.", 330, null],
  ["dawn", ["FFC", "ENGRO"], "other", "Fertiliser offtake slips in August as urea stocks build up", "Urea sales fell month on month, adding to inventory at producers.", 420, ["bearish", 0.79]],
  ["ogra", [], "fuel_price", "OGRA notifies revised LPG price for the month", "The regulator has announced the new LPG price. The change affects gas marketing companies.", 500, null],
  ["br", ["HBL", "UBL", "MEBL"], "other", "Bank profits may face pressure as interest rates ease", "Analysts expect lower yields on government papers to squeeze margins in the coming quarters.", 600, ["bearish", 0.83]],
  ["psx", ["LUCK"], "results", "Financial Results for the Year Ended June 30, 2026", "Lucky Cement has filed its annual results. See the notice for earnings per share and dividend details.", 720, null],
  ["mof", [], "budget_tax", "Finance Division issues SRO revising duty on selected imports", "A new SRO changes customs duty on some import items. Read the SRO for the full list.", 900, null],
  ["psx", ["ENGRO"], "board_meeting", "Board meeting in progress", "The Engro Corporation board meeting is under way. Outcomes will be announced to PSX.", 1180, null],
  ["secp", [], "regulatory", "SECP invites public comments on draft corporate governance amendments", "The regulator has opened a consultation on changes to the listed companies governance rules.", 1350, null],
  ["dawn", [], "other", "KSE-100 ends flat as investors stay cautious", "The benchmark index closed little changed on thin volumes.", 1480, ["neutral", 0.71]],
  ["psx", ["PSO"], "company_notice", "Book closure notice", "PSO has announced book closure dates to determine shareholder entitlement. See the notice.", 1600, null],
  ["mettis", ["SYS"], "other", "IT exports hit a new monthly high", "Software and services exports rose again, helped by strong demand from Gulf and US clients.", 1900, ["bullish", 0.88]],
  ["psx", ["HUBC"], "results", "Financial Results for the Year Ended June 30, 2026", "Hub Power has filed its results. Check the notice for profit, EPS and any dividend.", 2300, null],
  ["br", ["HUBC"], "other", "Power sector circular debt keeps pressure on IPPs", "Delayed payments continue to weigh on the cash flow of independent power producers.", 2600, ["bearish", 0.76]],
  ["psx", [], "regulatory", "PSX Notice: draft amendments to the Rule Book shared for comments", "The exchange has circulated draft rule changes and invited feedback from market participants.", 2900, null],
  ["dawn", ["PPL", "OGDC"], "other", "Oil and gas explorers eye new licences in upcoming bidding round", "Exploration companies are preparing bids as the government plans a new licensing round.", 3300, ["neutral", 0.68]],
  ["psx", ["MEBL"], "dividend", "Interim cash dividend announced", "Meezan Bank has announced an interim cash dividend. Entitlement details are in the notice.", 3900, null],
  ["mettis", ["UBL"], "other", "UBL expands digital banking services for retail customers", "The bank has rolled out new digital services aimed at everyday retail banking.", 4300, ["bullish", 0.72]],
  ["br", [], "other", "Rupee edges up against the dollar in interbank trade", "The local currency ended slightly stronger on modest dollar demand.", 4700, ["neutral", 0.66]],
  ["psx", ["FFC"], "board_meeting", "Notice of Board Meeting", "The FFC board will meet to consider the company's financial results.", 5200, null],
];
const makeSeed = () => SEED.map((d) => A(...d));

// Articles that "arrive" when the user refreshes or the 30 min job runs.
const FRESH = [
  () => A("psx", ["HBL"], "company_notice", "HBL | Notice of Annual General Meeting", "HBL has announced its annual general meeting. See the notice for the date and agenda.", 0, null),
  () => A("br", ["OGDC"], "other", "OGDC reports new gas discovery in Sindh", "The company says initial tests show commercial flow rates from the new well.", 0, ["bullish", 0.9]),
  () => A("dawn", ["LUCK"], "other", "Cement prices firm up in the north", "Dealers report higher bag prices after a rise in coal costs.", 0, ["bullish", 0.74]),
  () => A("sbp", [], "other", "SBP publishes weekly foreign exchange reserves data", "The central bank has released its latest weekly reserves figures.", 0, null),
];

/* ============================================================
   Helpers
   ============================================================ */
const pad = (n) => String(n).padStart(2, "0");
const fmtHM = (m) => `${pad(Math.floor(m / 60))}:${pad(m % 60)}`;
const fmtCountdown = (s) => `${Math.floor(s / 60)}:${pad(s % 60)}`;

function karachi(d) {
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone: "Asia/Karachi",
    weekday: "short",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).formatToParts(d);
  const p = {};
  parts.forEach((x) => {
    p[x.type] = x.value;
  });
  return {
    dow: ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].indexOf(p.weekday),
    day: p.weekday,
    date: `${p.year}-${p.month}-${p.day}`,
    mins: Number(p.hour) * 60 + Number(p.minute),
  };
}

function marketStatus(now) {
  const t = karachi(new Date(now));
  const wins = HOLIDAYS.includes(t.date) ? null : RUN_WINDOWS[t.dow];
  if (wins && wins.some(([s, e]) => t.mins >= s && t.mins <= e)) {
    return { open: true, label: "Market open" };
  }
  for (let i = 0; i <= 8; i++) {
    const n = karachi(new Date(now + i * 86400000));
    const w = HOLIDAYS.includes(n.date) ? null : RUN_WINDOWS[n.dow];
    if (!w) continue;
    const start = w[0][0];
    if (i === 0 && n.mins >= start) continue;
    return { open: false, label: `Opens ${i === 0 ? "today" : n.day} ${fmtHM(start)}` };
  }
  return { open: false, label: "Market closed" };
}

function timeAgo(iso, now) {
  const m = Math.floor((now - new Date(iso).getTime()) / 60000);
  if (m < 1) return "Just now";
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  if (h < 48) return "Yesterday";
  return new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short" });
}

const AVATAR = [
  "bg-blue-50 text-blue-700",
  "bg-emerald-50 text-emerald-700",
  "bg-violet-50 text-violet-700",
  "bg-amber-50 text-amber-700",
  "bg-rose-50 text-rose-700",
  "bg-sky-50 text-sky-700",
];
const avatarColor = (s) => AVATAR[[...s].reduce((a, c) => a + c.charCodeAt(0), 0) % AVATAR.length];

const CLAMP_2 = {
  display: "-webkit-box",
  WebkitLineClamp: 2,
  WebkitBoxOrient: "vertical",
  overflow: "hidden",
};

/* ============================================================
   UI pieces
   ============================================================ */
function Avatar({ item, size = "h-10 w-10" }) {
  const first = item.symbols[0]?.symbol;
  const label = first || item.source.name.replace(/[^A-Z]/g, "").slice(0, 4) || item.source.name.slice(0, 3);
  const color = avatarColor(first || item.source.key);
  const Badge = item.is_official ? Landmark : Newspaper;
  return (
    <div className={`relative flex-none ${size}`}>
      <div className={`flex h-full w-full items-center justify-center rounded-full border border-slate-200 text-xs font-bold tracking-tight ${color}`}>
        {label.slice(0, 4)}
      </div>
      <span className="absolute -bottom-0.5 -right-0.5 flex h-4 w-4 items-center justify-center rounded-full border-2 border-white bg-slate-400 text-white">
        <Badge size={9} />
      </span>
    </div>
  );
}

function NewsCard({ item, now, onOpenStock, onShare }) {
  const s = item.sentiment ? SENTIMENT[item.sentiment.label] : null;
  return (
    <article className="flex gap-4 border-b border-slate-100 px-6 py-5 hover:bg-slate-50">
      <Avatar item={item} />
      <div className="min-w-0 flex-1">
        <div className="flex items-start justify-between gap-3">
          <div className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1 text-sm">
            {item.symbols.length > 0 ? (
              item.symbols.slice(0, 3).map((sym) => (
                <button
                  key={sym.symbol}
                  type="button"
                  title={sym.name}
                  onClick={() => onOpenStock(sym.symbol)}
                  className="font-semibold text-slate-900 hover:text-blue-600 hover:underline"
                >
                  {sym.symbol}
                </button>
              ))
            ) : (
              <span className="font-semibold text-slate-900">{item.source.name}</span>
            )}
            {item.symbols.length > 0 && <span className="text-xs text-slate-400">{item.source.name}</span>}
            {item.is_official && (
              <span className="rounded bg-emerald-50 px-1.5 py-0.5 text-xs font-medium text-emerald-700">Official</span>
            )}
          </div>
          <span className="flex-none whitespace-nowrap text-xs text-slate-400">{timeAgo(item.published_at, now)}</span>
        </div>

        <h3 className="mt-1 text-sm font-medium text-slate-800">{item.title}</h3>
        {item.summary && (
          <p className="mt-1 text-sm text-slate-500" style={CLAMP_2}>
            {item.summary}
          </p>
        )}

        <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-400">
          <button
            type="button"
            onClick={() => onShare(item)}
            className="inline-flex items-center gap-1 hover:text-slate-700"
            aria-label="Copy link"
          >
            <Share2 size={13} />
          </button>
          <a
            href={item.external_url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 font-medium text-blue-600 hover:underline"
          >
            Source <ExternalLink size={12} />
          </a>
          {s && (
            <span className="inline-flex items-center gap-1.5 text-slate-500">
              <span className={`h-2 w-2 rounded-full ${s.dot}`} />
              {s.label}
            </span>
          )}
          <span className="rounded-full bg-slate-100 px-2 py-0.5 text-slate-500">{EVENT_LABEL[item.event_type]}</span>
        </div>
      </div>
    </article>
  );
}

function SkeletonRows() {
  return (
    <div>
      {[0, 1, 2, 3].map((i) => (
        <div key={i} className="flex animate-pulse gap-4 border-b border-slate-100 px-6 py-5">
          <div className="h-10 w-10 rounded-full bg-slate-100" />
          <div className="flex-1 space-y-2">
            <div className="h-3 w-40 rounded bg-slate-100" />
            <div className="h-3 w-3/4 rounded bg-slate-100" />
            <div className="h-3 w-1/2 rounded bg-slate-100" />
          </div>
        </div>
      ))}
    </div>
  );
}

function Empty({ title, text, action }) {
  return (
    <div className="px-6 py-16 text-center">
      <p className="text-sm font-semibold text-slate-800">{title}</p>
      <p className="mx-auto mt-1 max-w-sm text-sm text-slate-500">{text}</p>
      {action}
    </div>
  );
}

// Cursor-style "load more" over an already filtered list.
function Feed({ items, now, onOpenStock, onShare, empty }) {
  const [visible, setVisible] = useState(PAGE_SIZE);
  if (items.length === 0) return empty;
  return (
    <div>
      {items.slice(0, visible).map((it) => (
        <NewsCard key={it.id} item={it} now={now} onOpenStock={onOpenStock} onShare={onShare} />
      ))}
      {visible < items.length && (
        <div className="flex justify-center px-6 py-5">
          <button
            type="button"
            onClick={() => setVisible((v) => v + PAGE_SIZE)}
            className="rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            Load more
          </button>
        </div>
      )}
    </div>
  );
}

function Chip({ active, onClick, children }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-full border px-3 py-1.5 text-xs font-medium ${
        active
          ? "border-slate-900 bg-slate-900 text-white"
          : "border-slate-200 bg-white text-slate-600 hover:bg-slate-50"
      }`}
    >
      {children}
    </button>
  );
}

/* Stock page: the News tab shows only that stock's news and announcements. */
function StockPage({ symbol, items, now, onBack, onOpenStock, onShare }) {
  const [tab, setTab] = useState("news");
  const list = items.filter((a) => a.symbols.some((s) => s.symbol === symbol));
  return (
    <div className="mx-auto max-w-6xl px-6 py-10">
      <button type="button" onClick={onBack} className="inline-flex items-center gap-1.5 text-sm font-medium text-slate-500 hover:text-slate-900">
        <ArrowLeft size={16} /> Back to news
      </button>
      <div className="mt-5 flex items-center gap-4">
        <div className={`flex h-14 w-14 items-center justify-center rounded-full border border-slate-200 text-sm font-bold ${avatarColor(symbol)}`}>
          {symbol.slice(0, 4)}
        </div>
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-slate-900">{symbol}</h1>
          <p className="text-sm text-slate-500">{UNIVERSE[symbol] || symbol}</p>
        </div>
      </div>

      <div className="mt-6 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
        <div className="flex gap-2 border-b border-slate-200 p-4">
          {[
            ["overview", "Overview"],
            ["news", `News ${list.length}`],
          ].map(([k, label]) => (
            <button
              key={k}
              type="button"
              onClick={() => setTab(k)}
              className={`rounded-lg px-3.5 py-2 text-sm font-semibold ${
                tab === k ? "bg-slate-900 text-white" : "text-slate-500 hover:text-slate-900"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
        {tab === "overview" ? (
          <Empty title="Stock overview" text="Price, chart and fundamentals for this stock go here. Open the News tab to see its announcements." />
        ) : (
          <Feed
            key={symbol}
            items={list}
            now={now}
            onOpenStock={onOpenStock}
            onShare={onShare}
            empty={<Empty title={`No news for ${symbol} yet`} text="New announcements and stories will show up here as they arrive." />}
          />
        )}
      </div>
    </div>
  );
}

/* ============================================================
   Screen
   ============================================================ */
export default function MarketNews() {
  const [articles, setArticles] = useState(makeSeed);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState("news"); // news | portfolio
  const [chip, setChip] = useState("all");
  const [query, setQuery] = useState("");
  const [holdings, setHoldings] = useState(["HBL", "OGDC", "LUCK", "ENGRO"]);
  const [stock, setStock] = useState(null);
  const [now, setNow] = useState(Date.now());
  const [refreshing, setRefreshing] = useState(false);
  const [lastSuccessAt, setLastSuccessAt] = useState(Date.now() - 6 * 60000);
  const [toast, setToast] = useState(null);

  const lastRunRef = useRef(Date.now() - (REFRESH_COOLDOWN_SEC + 60) * 1000);
  const runningRef = useRef(false);
  const freshIdx = useRef(0);
  const toastTimer = useRef(null);

  const showToast = useCallback((msg) => {
    setToast(msg);
    clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToast(null), 2600);
  }, []);

  // Stands in for the Celery job + POST /news/refresh.
  const runIngestion = useCallback(async () => {
    if (runningRef.current) return { status: "already_running", added: 0 };
    runningRef.current = true;
    setRefreshing(true);
    lastRunRef.current = Date.now();
    await new Promise((r) => setTimeout(r, 1200));
    const fresh = FRESH.slice(freshIdx.current, freshIdx.current + 2).map((f) => f());
    freshIdx.current += fresh.length;
    if (fresh.length) setArticles((prev) => [...fresh, ...prev]);
    setLastSuccessAt(Date.now());
    runningRef.current = false;
    setRefreshing(false);
    return { status: "done", added: fresh.length };
  }, []);

  // Initial load.
  useEffect(() => {
    const t = setTimeout(() => setLoading(false), 700);
    return () => clearTimeout(t);
  }, []);

  // 1s clock: relative times, cooldown, and the 30 min job that only runs in market hours.
  useEffect(() => {
    const id = setInterval(() => {
      const t = Date.now();
      setNow(t);
      if (marketStatus(t).open && t - lastRunRef.current >= AUTO_INTERVAL_MS) runIngestion();
    }, 1000);
    return () => clearInterval(id);
  }, [runIngestion]);

  const onRefresh = async () => {
    if (runningRef.current) return;
    const left = Math.ceil(REFRESH_COOLDOWN_SEC - (Date.now() - lastRunRef.current) / 1000);
    if (left > 0) {
      showToast(`Already up to date. Try again in ${fmtCountdown(left)}.`);
      return;
    }
    const res = await runIngestion();
    showToast(res.added > 0 ? `${res.added} new ${res.added === 1 ? "article" : "articles"}` : "Already up to date.");
  };

  const onShare = async (item) => {
    try {
      await navigator.clipboard.writeText(item.external_url);
      showToast("Link copied");
    } catch (e) {
      showToast("Could not copy the link");
    }
  };

  const openStock = (sym) => {
    setStock(sym);
    window.scrollTo?.({ top: 0 });
  };

  const sorted = useMemo(
    () => [...articles].sort((a, b) => new Date(b.published_at) - new Date(a.published_at) || b.id - a.id),
    [articles]
  );

  const inPortfolio = useMemo(
    () => sorted.filter((a) => a.symbols.some((s) => holdings.includes(s.symbol))),
    [sorted, holdings]
  );

  const q = query.trim().toLowerCase();
  const list = useMemo(() => {
    const base = tab === "portfolio" ? inPortfolio : sorted;
    return base.filter((a) => {
      if (chip !== "all") {
        if (tab === "news" ? a.source.key !== chip : a.event_type !== chip) return false;
      }
      if (!q) return true;
      const hay = [a.title, a.summary, a.source.name, ...a.symbols.flatMap((s) => [s.symbol, s.name])]
        .join(" ")
        .toLowerCase();
      return hay.includes(q);
    });
  }, [tab, chip, q, sorted, inPortfolio]);

  const status = marketStatus(now);
  const cooldownLeft = Math.max(0, Math.ceil(REFRESH_COOLDOWN_SEC - (now - lastRunRef.current) / 1000));
  const officialCount = sorted.filter((a) => a.is_official).length;
  const mediaCount = sorted.length - officialCount;
  const available = Object.keys(UNIVERSE).filter((s) => !holdings.includes(s));

  const switchTab = (t) => {
    setTab(t);
    setChip("all");
  };

  if (stock) {
    return (
      <div className="min-h-screen bg-slate-50 text-slate-900">
        <StockPage symbol={stock} items={sorted} now={now} onBack={() => setStock(null)} onOpenStock={openStock} onShare={onShare} />
        <Toast msg={toast} />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <div className="mx-auto max-w-6xl px-6 py-10">
        <div className="mb-6 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
          Demo page with dummy data. No network calls are made.
        </div>

        {/* Header */}
        <div className="flex items-center gap-2 text-xs font-medium tracking-widest text-slate-500">
          <span className="relative flex h-2 w-2">
            {status.open && <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />}
            <span className={`relative inline-flex h-2 w-2 rounded-full ${status.open ? "bg-emerald-500" : "bg-slate-400"}`} />
          </span>
          {status.open ? "LIVE FEED" : "MARKET CLOSED"}
        </div>
        <h1 className="mt-3 text-4xl font-bold tracking-tight text-slate-900">Market News</h1>
        <p className="mt-3 max-w-xl text-sm leading-6 text-slate-500">
          Announcements and news from <span className="font-semibold text-slate-800">PSX, SECP, SBP, OGRA, the Finance Ministry</span> and
          leading business outlets. Short summaries, with a link to the original.
        </p>

        {/* Stats + refresh */}
        <div className="mt-6 flex flex-wrap items-center justify-between gap-4">
          <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-sm text-slate-500">
            <span className="text-lg font-semibold text-slate-900">{sorted.length}</span>
            <span className="h-4 w-px bg-slate-200" />
            <span className="inline-flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-sky-500" /><b className="font-semibold text-slate-700">{officialCount}</b> Official</span>
            <span className="inline-flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-violet-500" /><b className="font-semibold text-slate-700">{mediaCount}</b> News</span>
            <span className="inline-flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-amber-500" /><b className="font-semibold text-slate-700">{inPortfolio.length}</b> For your stocks</span>
          </div>
          <div className="flex items-center gap-3">
            <span className={`rounded-full border px-2.5 py-1 text-xs font-medium ${status.open ? "border-emerald-200 bg-emerald-50 text-emerald-700" : "border-slate-200 bg-white text-slate-500"}`}>
              {status.label}
            </span>
            <span className="hidden text-xs text-slate-400 sm:inline">Updated {timeAgo(new Date(lastSuccessAt).toISOString(), now)}</span>
            <button
              type="button"
              onClick={onRefresh}
              disabled={refreshing}
              title={cooldownLeft > 0 ? `Refresh available in ${fmtCountdown(cooldownLeft)}` : "Get the latest news now"}
              className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-60"
            >
              <RefreshCw size={14} className={refreshing ? "animate-spin" : ""} />
              {refreshing ? "Refreshing" : "Refresh"}
            </button>
          </div>
        </div>

        {/* Card */}
        <div className="mt-5 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
          <div className="flex flex-col gap-3 border-b border-slate-200 p-4 md:flex-row md:items-center md:justify-between">
            <div className="flex gap-2">
              {[
                ["news", "News", sorted.length],
                ["portfolio", "Portfolio", inPortfolio.length],
              ].map(([k, label, count]) => (
                <button
                  key={k}
                  type="button"
                  onClick={() => switchTab(k)}
                  className={`rounded-lg px-3.5 py-2 text-sm font-semibold ${
                    tab === k ? "bg-slate-900 text-white" : "text-slate-500 hover:text-slate-900"
                  }`}
                >
                  {label}
                  <span className={`ml-2 text-xs ${tab === k ? "text-slate-300" : "text-slate-400"}`}>{count}</span>
                </button>
              ))}
            </div>
            <div className="relative w-full md:w-72">
              <Search size={16} className="pointer-events-none absolute left-3 top-1/2 transform -translate-y-1/2 text-slate-400" />
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search company or keyword..."
                className="w-full rounded-lg border border-slate-200 py-2 pl-9 pr-3 text-sm text-slate-800 placeholder-slate-400 focus:border-slate-300 focus:outline-none focus:ring-2 focus:ring-slate-200"
              />
            </div>
          </div>

          {/* Row filters */}
          {tab === "portfolio" && (
            <div className="flex flex-wrap items-center gap-2 border-b border-slate-100 bg-slate-50 px-4 py-3">
              <span className="mr-1 text-xs font-medium text-slate-500">Your stocks</span>
              {holdings.map((s) => (
                <span key={s} className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-white py-1 pl-2.5 pr-1.5 text-xs font-medium text-slate-700">
                  {s}
                  <button type="button" aria-label={`Remove ${s}`} onClick={() => setHoldings((h) => h.filter((x) => x !== s))} className="rounded-full p-0.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700">
                    <X size={12} />
                  </button>
                </span>
              ))}
              {available.length > 0 && (
                <select
                  value=""
                  onChange={(e) => e.target.value && setHoldings((h) => [...h, e.target.value])}
                  className="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-xs text-slate-600 focus:outline-none"
                >
                  <option value="">Add stock</option>
                  {available.map((s) => (
                    <option key={s} value={s}>{s}</option>
                  ))}
                </select>
              )}
            </div>
          )}
          <div className="flex flex-wrap gap-2 border-b border-slate-100 px-4 py-3">
            {tab === "news"
              ? [["all", "All"], ...Object.entries(SOURCES).map(([k, v]) => [k, v.name])].map(([k, label]) => (
                  <Chip key={k} active={chip === k} onClick={() => setChip(k)}>
                    {k !== "all" && SOURCES[k].type === "official" && <span className="mr-1.5 inline-block h-1.5 w-1.5 rounded-full bg-emerald-500" />}
                    {label}
                  </Chip>
                ))
              : PORTFOLIO_CHIPS.map(([k, label]) => (
                  <Chip key={k} active={chip === k} onClick={() => setChip(k)}>
                    {label}
                  </Chip>
                ))}
          </div>

          {/* Feed */}
          {loading ? (
            <SkeletonRows />
          ) : (
            <Feed
              key={`${tab}-${chip}-${q}-${holdings.join()}`}
              items={list}
              now={now}
              onOpenStock={openStock}
              onShare={onShare}
              empty={
                tab === "portfolio" && holdings.length === 0 ? (
                  <Empty
                    title="Add stocks to see your news"
                    text="Announcements and news for the stocks you hold will show up here."
                    action={
                      <button type="button" onClick={() => setHoldings(["HBL", "OGDC", "LUCK"])} className="mt-4 rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800">
                        Add stocks
                      </button>
                    }
                  />
                ) : (
                  <Empty
                    title={q ? "No results" : tab === "portfolio" ? "No news for your stocks yet" : "No news yet"}
                    text={q ? "Try a different company name or keyword." : "New announcements and stories will show up here as they arrive."}
                  />
                )
              }
            />
          )}

          <div className="border-t border-slate-100 px-6 py-4 text-xs text-slate-400">
            Summaries only. Tap Source to read the original. Updates every 30 minutes during market hours (Mon to Thu 09:15 to 15:30, Fri 09:00 to 16:30 PKT). Not investment advice.
          </div>
        </div>
      </div>
      <Toast msg={toast} />
    </div>
  );
}

function Toast({ msg }) {
  if (!msg) return null;
  return (
    <div className="pointer-events-none fixed inset-x-0 bottom-6 flex justify-center px-4">
      <div className="rounded-lg bg-slate-900 px-4 py-2 text-sm text-white shadow-lg">{msg}</div>
    </div>
  );
}