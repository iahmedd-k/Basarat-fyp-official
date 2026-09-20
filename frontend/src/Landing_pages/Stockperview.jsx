import React, { useState } from "react";
import {
  AreaChart,
  Area,
  Bar,
  ComposedChart,
  BarChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";
import { ExternalLink, Search } from "lucide-react";

/**
 * Single-page stock detail preview — Overview / Income Statement /
 * Balance Sheet / Cash Flow / Technicals / Ratios / Peers / Activities.
 * All charts are real recharts components driven by dummy data; the
 * dummy figures are kept internally consistent across tabs (e.g. the
 * Net Income used in the FY bar chart matches the EPS shown in Ratios
 * and the Peers table row for MDTL).
 *
 * Font: pins Inter explicitly, same approach as the other pages in
 * this project — delete the <link> tags if Inter is already loaded
 * globally in your app.
 */

const FONT_STACK =
  "'Inter', ui-sans-serif, system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif";

/* ================================ dummy data ================================ */

const COMPANY = {
  name: "Media Times Limited",
  symbol: "MDTL",
  sector: "TECHNOLOGY & COMMUNICATION",
  rank: "17th of 21 by market cap",
};

const TABS = [
  "Overview",
  "Income Statement",
  "Balance Sheet",
  "Cash Flow",
  "Technicals",
  "Ratios",
  "Peers",
  "Activities",
];

// Intraday 1D price series, 15m interval, 09:15 - 16:00
const INTRADAY = [
  { t: "09:15", price: 7.6, vol: 1.1, down: false },
  { t: "09:30", price: 7.65, vol: 0.9, down: false },
  { t: "09:45", price: 7.72, vol: 1.4, down: false },
  { t: "10:00", price: 7.85, vol: 1.6, down: false },
  { t: "10:15", price: 7.8, vol: 2.1, down: true },
  { t: "10:30", price: 8.1, vol: 2.4, down: false },
  { t: "10:45", price: 8.16, vol: 1.5, down: false },
  { t: "11:00", price: 8.22, vol: 1.3, down: false },
  { t: "11:15", price: 8.18, vol: 1.9, down: true },
  { t: "11:30", price: 8.2, vol: 1.2, down: false },
  { t: "11:45", price: 8.21, vol: 0.9, down: false },
  { t: "12:00", price: 8.23, vol: 1.0, down: false },
  { t: "12:15", price: 8.26, vol: 0.8, down: false },
  { t: "12:30", price: 8.3, vol: 1.1, down: false },
  { t: "12:45", price: 8.29, vol: 0.7, down: false },
  { t: "13:00", price: 8.31, vol: 0.9, down: false },
  { t: "13:15", price: 8.33, vol: 1.0, down: false },
  { t: "13:30", price: 8.32, vol: 0.8, down: false },
  { t: "14:00", price: 8.34, vol: 1.2, down: false },
  { t: "14:30", price: 8.4, vol: 1.6, down: false },
  { t: "15:00", price: 8.55, vol: 3.4, down: false },
  { t: "15:15", price: 8.6, vol: 1.2, down: false },
  { t: "15:30", price: 8.6, vol: 0.9, down: false },
  { t: "16:00", price: 8.6, vol: 0.7, down: false },
];

const SIDEBAR_STATS = {
  prevClose: "7.60",
  open: "7.60",
  dayChange: "+1.00",
  dayChangePct: "+13.16%",
  volume: "69.65M",
  ytdReturn: "+123.96%",
  dayRangeLow: "7.60",
  dayRangeHigh: "8.60",
  weekRangeLow: "3.80",
  weekRangeHigh: "9.30",
};

const KEY_METRICS = [
  { label: "Score 3.6", score: 3.6, hasScore: true },
  { label: "Valuation", score: 3.2 },
  { label: "Quality", score: 2.2 },
  { label: "Health", score: 1.8 },
  { label: "Growth", score: 4.0 },
  { label: "Technical", score: 4.2 },
];

const TOP_STATS = [
  { label: "Revenue", badge: "Top tier", badgeType: "good", value: "Rs. 153.0 M", sub: "+128.4% YoY · sector 10.1%" },
  { label: "Net Profit", badge: "Loss-making", badgeType: "bad", value: "Rs. -1.00 M", sub: "+66.7% YoY · sector 15.8%", valueBad: true },
  { label: "EPS", badge: "Loss-making", badgeType: "bad", value: "Rs-0.00", sub: "Sector growth 15.8%", valueBad: true },
  { label: "ROE", badge: "Distorted", badgeType: "bad", value: "-6.3%", sub: "vs sector 11.7%", valueBad: true },
  { label: "P/E", value: "N/A", sub: "vs sector 15.2x" },
  { label: "Div Yield", badge: "Above sector", badgeType: "good", value: "0.0%", sub: "vs sector 0.0%" },
];

const FY_LABELS = ["FY 2021", "FY 2022", "FY 2023", "FY 2024", "FY 2025", "TTM"];

const REVENUE_CHART = [121, 151, 111, 67, 153, 160].map((v, i) => ({
  name: FY_LABELS[i],
  value: v,
  ttm: i === 5,
}));
const EBITDA_CHART = [-41, -1, -39, -51, 36, 40].map((v, i) => ({
  name: FY_LABELS[i],
  value: v,
  ttm: i === 5,
}));
const NET_INCOME_CHART = [-114, 18, -110, -3, -1, -1].map((v, i) => ({
  name: FY_LABELS[i],
  value: v,
  ttm: i === 5,
}));
const EARNINGS_DIVIDENDS_CHART = [
  { name: "FY 2021", eps: -0.64, dps: 0, payout: 0 },
  { name: "FY 2022", eps: 0.1, dps: 0, payout: 0 },
  { name: "FY 2023", eps: -0.61, dps: 0, payout: 0 },
  { name: "FY 2024", eps: -0.02, dps: 0, payout: 0 },
  { name: "FY 2025", eps: -0.01, dps: 0, payout: 0 },
  { name: "TTM", eps: -0.01, dps: 0, payout: 0, ttm: true },
];

const COMPANY_PROFILE = {
  about:
    "Media Times Limited was incorporated in Pakistan on 26 June 2001 as a private limited company and was converted into a public limited company on 06 March 2007. The Company is primarily involved in printing and publishing daily English and Urdu newspapers under the names \"Daily Times\" and \"AajKal\" respectively.",
  info: [
    { label: "Registered Address", value: "First Capital House, 96-B/1, Lower Ground Floor, M.M. Alam Road, Gulberg-III, Lahore" },
    { label: "Website", value: "www.pacepakistan.com", link: true },
    { label: "Auditor", value: "Junaidy Shoaib Asad Chartered Accountants" },
    { label: "Registrar", value: "Corplink (Pvt.) Limited Wings Arcade, 1-K Commercial Model Town, Lahore" },
    { label: "Fiscal Year End", value: "June" },
  ],
  people: [
    { name: "Shehryar Ali Taseer", role: "CEO" },
    { name: "Aamna Taseer", role: "Chairperson" },
    { name: "Shahzad Jawahar", role: "Company Secretary" },
  ],
  shares: { total: "178.85M", freeFloat: "116.25M", freeFloatPct: "65%" },
};

const YEARS8 = ["FY 2025", "FY 2024", "FY 2023", "FY 2022", "FY 2021", "FY 2020", "FY 2019", "FY 2018"];

function row(label, cells) {
  return { label, values: cells.map(([v, yoy]) => ({ v, yoy, pos: yoy?.startsWith("+") ? true : yoy === "0.0%" ? null : false })) };
}

const INCOME_STATEMENT = [
  {
    title: "Revenue",
    rows: [
      row("Total Revenue", [
        ["Rs. 153.0 M", "+128.4%"], ["Rs. 67.00 M", "-39.6%"], ["Rs. 111.0 M", "-26.5%"], ["Rs. 151.0 M", "+24.8%"],
        ["Rs. 121.0 M", "-22.4%"], ["Rs. 156.0 M", "-11.9%"], ["Rs. 177.0 M", "-50.1%"], ["Rs. 355.0 M", "-8.0%"],
      ]),
      row("Gross Profit", [
        ["Rs. 69.00 M", "+445.0%"], ["Rs. -20.00 M", "-1100.0%"], ["Rs. 2.00 M", "-95.2%"], ["Rs. 42.00 M", "+500.0%"],
        ["Rs. 7.00 M", "-61.1%"], ["Rs. 18.00 M", "+205.9%"], ["Rs. -17.00 M", "-143.6%"], ["Rs. 39.00 M", "-18.8%"],
      ]),
    ],
  },
  {
    title: "Operating",
    rows: [
      row("PBIT", [
        ["Rs. 10.00 M", "+112.5%"], ["Rs. -80.00 M", "-12.7%"], ["Rs. -71.00 M", "-102.9%"], ["Rs. -35.00 M", "+59.8%"],
        ["Rs. -87.00 M", "-31.8%"], ["Rs. -66.00 M", "+56.0%"], ["Rs. -150.0 M", "+12.3%"], ["Rs. -171.0 M", "-69.3%"],
      ]),
      row("EBITDA", [
        ["Rs. 36.00 M", "+170.6%"], ["Rs. -51.00 M", "-30.8%"], ["Rs. -39.00 M", "-3800.0%"], ["Rs. -1.00 M", "+97.6%"],
        ["Rs. -41.00 M", "-127.8%"], ["Rs. -18.00 M", "+81.1%"], ["Rs. -95.00 M", "+5.0%"], ["Rs. -100.0 M", "-900.0%"],
      ]),
      row("Financial Charges", [
        ["Rs. -65.00 M", "+32.3%"], ["Rs. -96.00 M", "+9.4%"], ["Rs. -106.0 M", "-47.2%"], ["Rs. -72.00 M", "-41.2%"],
        ["Rs. -51.00 M", "+1.9%"], ["Rs. -52.00 M", "0.0%"], ["Rs. -52.00 M", "+23.5%"], ["Rs. -68.00 M", "-223.8%"],
      ]),
    ],
  },
  {
    title: "Pre-tax & tax",
    rows: [
      row("PBT", [
        ["Rs. 1.00 M", "+150.0%"], ["Rs. -2.00 M", "+98.2%"], ["Rs. -109.0 M", "-619.0%"], ["Rs. 21.00 M", "+118.9%"],
        ["Rs. -111.0 M", "-2.8%"], ["Rs. -108.0 M", "+55.7%"], ["Rs. -244.0 M", "-11.4%"], ["Rs. -219.0 M", "-195.9%"],
      ]),
      row("Taxation", [
        ["Rs. -2.00 M", "-100.0%"], ["Rs. -1.00 M", "0.0%"], ["Rs. -1.00 M", "+66.7%"], ["Rs. -3.00 M", "0.0%"],
        ["Rs. -3.00 M", "-50.0%"], ["Rs. -2.00 M", "-100.0%"], ["Rs. -1.00 M", "+90.0%"], ["Rs. -10.00 M", "-66.7%"],
      ]),
      row("Net Income", [
        ["Rs. -1.00 M", "+66.7%"], ["Rs. -3.00 M", "+97.3%"], ["Rs. -110.0 M", "-644.4%"], ["Rs. 18.00 M", "+115.8%"],
        ["Rs. -114.0 M", "-3.6%"], ["Rs. -110.0 M", "+53.0%"], ["Rs. -245.0 M", "-11.5%"], ["Rs. -229.0 M", "-186.4%"],
      ]),
    ],
  },
];

const BALANCE_SHEET = [
  {
    title: "Assets",
    rows: [
      row("Cash and Equivalents", [
        ["Rs. 8.00 M", "+700.0%"], ["Rs. 1.00 M", "0.0%"], ["Rs. 1.00 M", "-75.0%"], ["Rs. 4.00 M", "-33.3%"],
        ["Rs. 6.00 M", "+100.0%"], ["Rs. 3.00 M", "+200.0%"], ["Rs. 1.00 M", "0.0%"], ["Rs. 1.00 M", "-66.7%"],
      ]),
      row("Current Assets", [
        ["Rs. 56.00 M", "+64.7%"], ["Rs. 34.00 M", "-5.6%"], ["Rs. 36.00 M", "-35.7%"], ["Rs. 56.00 M", "+30.2%"],
        ["Rs. 43.00 M", "-23.2%"], ["Rs. 56.00 M", "+12.0%"], ["Rs. 50.00 M", "-59.7%"], ["Rs. 124.0 M", "-19.5%"],
      ]),
      row("Non Current Assets", [
        ["Rs. 86.00 M", "-57.6%"], ["Rs. 203.0 M", "-12.1%"], ["Rs. 231.0 M", "-36.2%"], ["Rs. 362.0 M", "+22.7%"],
        ["Rs. 295.0 M", "+30.5%"], ["Rs. 226.0 M", "-18.1%"], ["Rs. 276.0 M", "-19.1%"], ["Rs. 341.0 M", "-19.6%"],
      ]),
      row("Total Assets", [
        ["Rs. 142.0 M", "-40.1%"], ["Rs. 237.0 M", "-11.2%"], ["Rs. 267.0 M", "-36.1%"], ["Rs. 418.0 M", "+23.7%"],
        ["Rs. 338.0 M", "+19.9%"], ["Rs. 282.0 M", "-13.5%"], ["Rs. 326.0 M", "-29.9%"], ["Rs. 465.0 M", "-19.6%"],
      ]),
    ],
  },
  {
    title: "Liabilities",
    rows: [
      row("Current Liabilities", [
        ["Rs. 838.0 M", "+2.7%"], ["Rs. 816.0 M", "-9.5%"], ["Rs. 902.0 M", "+9.2%"], ["Rs. 826.0 M", "+5.6%"],
        ["Rs. 782.0 M", "-7.1%"], ["Rs. 842.0 M", "+8.4%"], ["Rs. 777.0 M", "+17.2%"], ["Rs. 663.0 M", "+10.9%"],
      ]),
      row("Non Current Liabilities", [
        ["Rs. 361.0 M", "-24.0%"], ["Rs. 475.0 M", "+13.9%"], ["Rs. 417.0 M", "-22.2%"], ["Rs. 536.0 M", "+4.3%"],
        ["Rs. 514.0 M", "+80.4%"], ["Rs. 285.0 M", "-2.1%"], ["Rs. 291.0 M", "+3.6%"], ["Rs. 281.0 M", "+23.8%"],
      ]),
      row("Total Liabilities", [
        ["Rs. 1.20 B", "-7.1%"], ["Rs. 1.29 B", "-2.1%"], ["Rs. 1.32 B", "-3.2%"], ["Rs. 1.36 B", "+5.1%"],
        ["Rs. 1.30 B", "+15.0%"], ["Rs. 1.13 B", "+5.5%"], ["Rs. 1.07 B", "+13.1%"], ["Rs. 944.0 M", "+14.4%"],
      ]),
    ],
  },
  {
    title: "Equity",
    rows: [
      row("Total Equity", [
        ["Rs. -1.06 B", "-0.5%"], ["Rs. -1.05 B", "-0.3%"], ["Rs. -1.05 B", "-11.6%"], ["Rs. -942.0 M", "+2.1%"],
        ["Rs. -962.0 M", "-13.4%"], ["Rs. -848.0 M", "-14.0%"], ["Rs. -744.0 M", "-55.3%"], ["Rs. -479.0 M", "-15.7%"],
      ]),
    ],
  },
];

const CASH_FLOW = [
  {
    title: "Operating",
    rows: [
      row("Operating Cash Flow", [
        ["Rs. 36.00 M", "+325.0%"], ["Rs. -16.00 M", "-113.1%"], ["Rs. 122.0 M", "+187.5%"], ["Rs. 0.00 M", "+100.0%"],
        ["Rs. -118.0 M", "-2850.0%"], ["Rs. -4.00 M", "+78.9%"], ["Rs. -19.00 M", "+70.8%"], ["Rs. -65.00 M", "-28.4%"],
      ]),
    ],
  },
  {
    title: "Investing",
    rows: [
      row("Capital Expenditure", [
        ["Rs. 90.00 M", "+9100.0%"], ["Rs. -1.00 M", "-99.1%"], ["Rs. 0.00 M", "+100.0%"], ["Rs. -1.00 M", "-99.1%"],
        ["Rs. -115.0 M", "-5850.0%"], ["Rs. 2.00 M", "-77.8%"], ["Rs. 9.00 M", "-25.0%"], ["Rs. 12.00 M", "+70.0%"],
      ]),
    ],
  },
  {
    title: "Free cash flow",
    rows: [
      row("Free Cash Flow to the Firm (FCFF)", [
        ["Rs. 61.00 M", "-52.0%"], ["Rs. 127.0 M", "-44.5%"], ["Rs. 229.0 M", "+277.2%"], ["Rs. 60.71 M", "+133.6%"],
        ["Rs. -180.6 M", "-454.4%"], ["Rs. 50.96 M", "+20.7%"], ["Rs. 42.21 M", "+133.1%"], ["Rs. 18.10 M", "+38.4%"],
      ]),
    ],
  },
];

const OSCILLATORS = [
  { label: "RSI (14)", value: "75.85", signal: "SELL" },
  { label: "RSI (7)", value: "82.67", signal: "SELL" },
  { label: "RSI (21)", value: "71.84", signal: "SELL" },
  { label: "Stochastic %K", value: "80.33 / 74.92", signal: "NEUTRAL" },
  { label: "MACD (12,26)", value: "0.56 / 0.36", signal: "BUY" },
  { label: "CCI (20)", value: "-470.19", signal: "BUY" },
];

const MOVING_AVERAGES = [
  { label: "SMA (5)", value: "7.84", pct: "+9.7%", signal: "STRONG BUY" },
  { label: "SMA (10)", value: "7.42", pct: "+15.9%", signal: "STRONG BUY" },
  { label: "SMA (20)", value: "6.51", pct: "+32.1%", signal: "STRONG BUY" },
  { label: "SMA (50)", value: "6.13", pct: "+40.3%", signal: "STRONG BUY" },
  { label: "SMA (100)", value: "6.01", pct: "+43.2%", signal: "STRONG BUY" },
  { label: "SMA (200)", value: "5.78", pct: "+48.7%", signal: "STRONG BUY" },
];

const VALUATION_METRICS = [
  { label: "P/E (TTM)", sub: "Price ÷ TTM EPS", value: "2.16x", good: true },
  { label: "P/B", sub: "Price ÷ book value per share", value: "0.00x" },
  { label: "P/S (TTM)", sub: "Price ÷ TTM sales per share", value: "8.50x" },
  { label: "PEG", sub: "P/E ÷ earnings growth %", value: "N/A" },
  { label: "EV / EBITDA", sub: "Enterprise value ÷ TTM EBITDA", value: "31.76x" },
  { label: "EV / Sales", sub: "Enterprise value ÷ TTM sales", value: "10.35x" },
  { label: "Earnings Yield", sub: "TTM earnings ÷ price (inverse P/E)", value: "46.35%", good: true },
  { label: "Dividend Yield", sub: "TTM dividend per share ÷ price", value: "0.00%" },
  { label: "FCF Yield", sub: "Free cash flow ÷ market cap", value: "0.00%" },
  { label: "CFO Yield", sub: "Operating cash flow ÷ market cap", value: "0.00%" },
  { label: "Cash / Market Cap", sub: "Cash & equivalents ÷ market cap", value: "0.33%" },
];

const PROFITABILITY_METRICS = [
  { label: "Gross Margin", sub: "Gross profit ÷ revenue", value: "54.70%", good: true },
  { label: "Operating Margin", sub: "Operating profit ÷ revenue", value: "20.99%", good: true },
  { label: "EBITDA Margin", sub: "EBITDA ÷ revenue", value: "32.60%", good: true },
  { label: "Net Margin", sub: "Net profit ÷ revenue", value: "393.37%", good: true },
  { label: "PBT Margin", sub: "Profit before tax ÷ revenue", value: "477.35%" },
  { label: "ROE", sub: "Net income ÷ shareholder equity", value: "-226.03%", bad: true },
  { label: "ROA", sub: "Net income ÷ total assets", value: "68.46%", good: true },
  { label: "ROCE", sub: "EBIT ÷ capital employed", value: "146.15%", good: true },
  { label: "ROIC", sub: "NOPAT ÷ invested capital", value: "-430.77%", bad: true },
  { label: "CFO Margin", sub: "Operating cash flow ÷ revenue", value: "0.00%" },
  { label: "FCF Margin", sub: "Free cash flow ÷ revenue", value: "0.00%" },
  { label: "Effective Tax Rate", sub: "Taxation ÷ profit before tax", value: "17.8%" },
];

const PEERS = [
  { symbol: "MDTL", name: "Media Times Limited", revenue: "Rs. 153.0 M", revGrowth: "+128.36%", profit: "Rs. -1.00 M", profitGrowth: "+66.67%", eps: "Rs-0.00", epsGrowth: "+80.00%", pe: "2.16", divYield: "0.00%", ytd: "+123.96%", current: true },
  { symbol: "PTC", name: "Pakistan Telecommunication Com...", revenue: "Rs. 251.7 B", revGrowth: "+12.25%", profit: "Rs. -9.75 B", profitGrowth: "+32.29%", eps: "Rs-1.91", epsGrowth: "+32.27%", pe: "66.81", divYield: "0.00%", ytd: "-4.02%" },
  { symbol: "SYS", name: "Systems Limited", revenue: "Rs. 80.39 B", revGrowth: "+19.15%", profit: "Rs. 11.04 B", profitGrowth: "+48.00%", eps: "Rs7.52", epsGrowth: "+47.16%", pe: "15.19", divYield: "1.64%", ytd: "-20.75%" },
  { symbol: "AIRLINK", name: "Air Link Communication Limited", revenue: "Rs. 104.4 B", revGrowth: "-19.55%", profit: "Rs. 4.75 B", profitGrowth: "+2.66%", eps: "Rs12.01", epsGrowth: "+2.65%", pe: "9.20", divYield: "5.04%", ytd: "-30.75%" },
  { symbol: "TRG", name: "TRG Pakistan Limited", revenue: "Rs. 2.00 M", revGrowth: "-33.33%", profit: "Rs. 3.92 B", profitGrowth: "+112.72%", eps: "Rs7.19", epsGrowth: "+112.71%", pe: "—", divYield: "0.00%", ytd: "-30.45%" },
  { symbol: "SELECT", name: "Select Technologies Limited", revenue: "—", revGrowth: "—", profit: "—", profitGrowth: "—", eps: "N/A", epsGrowth: "—", pe: "—", divYield: "0.00%", ytd: "—" },
  { symbol: "AVN", name: "Avanceon Limited", revenue: "Rs. 15.88 B", revGrowth: "-1.68%", profit: "Rs. 655.0 M", profitGrowth: "-68.22%", eps: "Rs1.51", epsGrowth: "-70.45%", pe: "28.35", divYield: "3.53%", ytd: "-35.05%" },
  { symbol: "NETSOL", name: "NetSol Technologies Limited", revenue: "Rs. 9.90 B", revGrowth: "+3.39%", profit: "Rs. 1.39 B", profitGrowth: "+15.13%", eps: "Rs15.74", epsGrowth: "+15.82%", pe: "3.99", divYield: "0.00%", ytd: "-14.95%" },
  { symbol: "HUMNL", name: "Hum Network Limited", revenue: "Rs. 11.48 B", revGrowth: "-6.62%", profit: "Rs. 1.24 B", profitGrowth: "-57.74%", eps: "Rs1.09", epsGrowth: "-57.75%", pe: "11.28", divYield: "5.04%", ytd: "-29.65%" },
  { symbol: "ZAL", name: "Zarea Limited", revenue: "Rs. 1.34 B", revGrowth: "+203.85%", profit: "Rs. 671.0 M", profitGrowth: "+129.01%", eps: "Rs3.04", epsGrowth: "-23.81%", pe: "9.56", divYield: "2.57%", ytd: "-18.25%" },
];

const ACTIVITIES = [
  { tags: ["Exchange Notice"], title: "Board Meeting", date: "2d ago" },
  { tags: ["Exchange Notice"], title: "Unusual movement in Volume of the Shares of Media Times Limited", date: "3d ago" },
  { tags: ["Exchange Notice"], title: "Appointment of Chief Executive Officer / Chairman of the Board", date: "Jul 1, 2026" },
  { tags: ["Exchange Notice"], title: "Certified Copy of Resolutions Passed by the Shareholders of Media Times Limited in its EOGM", date: "Jun 29, 2026" },
  { tags: ["Exchange Notice"], title: "Notice Under Section 159(4) of the Companies Act, 2017", date: "Jun 19, 2026" },
  { tags: ["Exchange Notice"], title: "Notice of Extraordinary General Meeting", date: "Jun 4, 2026" },
  { tags: ["Financial Result", "Quarterly Report"], title: "Quarterly accounts for the period ended 31 March 2026", date: "Apr 28, 2026" },
];

/* ============================== small building blocks ============================== */

function Pill({ active, onClick, children, className = "" }) {
  return (
    <button
      onClick={onClick}
      className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition ${
        active ? "bg-gray-900 text-white" : "text-gray-500 hover:bg-gray-100"
      } ${className}`}
    >
      {children}
    </button>
  );
}

function ChangeText({ pos, children }) {
  const cls = pos === null || pos === undefined ? "text-gray-400" : pos ? "text-emerald-600" : "text-red-500";
  return <span className={`text-xs font-medium ${cls}`}>{children}</span>;
}

function Dots({ score, max = 5 }) {
  return (
    <span className="inline-flex items-center gap-0.5">
      {Array.from({ length: max }).map((_, i) => (
        <span
          key={i}
          className={`h-1.5 w-1.5 rounded-full ${i < Math.round(score) ? "bg-emerald-500" : "bg-gray-200"}`}
        />
      ))}
    </span>
  );
}

function StatBadge({ type, children }) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-semibold ${
        type === "good" ? "bg-emerald-50 text-emerald-600" : "bg-red-50 text-red-500"
      }`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${type === "good" ? "bg-emerald-500" : "bg-red-500"}`} />
      {children}
    </span>
  );
}

function SignalBadge({ signal }) {
  const style =
    signal === "SELL"
      ? "bg-red-50 text-red-500"
      : signal === "NEUTRAL"
      ? "bg-gray-100 text-gray-500"
      : "bg-emerald-50 text-emerald-600";
  return (
    <span className={`inline-block rounded px-2 py-1 text-[10px] font-bold tracking-wide ${style}`}>
      {signal}
    </span>
  );
}

function SectionCard({ title, children, right }) {
  return (
    <div className="rounded-2xl border border-gray-100 bg-white p-6">
      {title && (
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-base font-bold text-gray-900">{title}</h3>
          {right}
        </div>
      )}
      {children}
    </div>
  );
}

function Gauge({ value, label, sublabel, sell, neutral, buy }) {
  const angle = -90 + Math.max(0, Math.min(1, value)) * 180;
  const color = value < 0.4 ? "#ef4444" : value < 0.6 ? "#f59e0b" : "#10b981";
  return (
    <div className="flex flex-col items-center">
      <span className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-gray-400">{label}</span>
      <svg viewBox="0 0 200 110" className="w-40">
        <defs>
          <linearGradient id={`grad-${label}`} x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#ef4444" />
            <stop offset="50%" stopColor="#f59e0b" />
            <stop offset="100%" stopColor="#10b981" />
          </linearGradient>
        </defs>
        <path
          d="M 15 100 A 85 85 0 0 1 185 100"
          fill="none"
          stroke={`url(#grad-${label})`}
          strokeWidth="14"
          strokeLinecap="round"
        />
        <g style={{ transform: `rotate(${angle}deg)`, transformOrigin: "100px 100px" }}>
          <line x1="100" y1="100" x2="100" y2="28" stroke="#111827" strokeWidth="3" strokeLinecap="round" />
        </g>
        <circle cx="100" cy="100" r="4.5" fill="#111827" />
      </svg>
      <span className="mt-1 text-lg font-bold" style={{ color }}>
        {sublabel}
      </span>
      <span className="mt-1 text-[11px] text-gray-400">
        <span className="text-red-500">— SELL {sell}</span>
        {"  "}
        <span className="text-gray-400">— NEUTRAL {neutral}</span>
        {"  "}
        <span className="text-emerald-500">— BUY {buy}</span>
      </span>
    </div>
  );
}

/* =================================== Overview tab =================================== */

function OverviewTab() {
  const [range, setRange] = useState("1D");
  const [interval, setIntervalSel] = useState("15m");
  const [perfMode, setPerfMode] = useState("Annual");

  const barColor = (ttm) => (ttm ? "#93c5fd" : "#3b82f6");

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_320px]">
        {/* Price history */}
        <SectionCard>
          <div className="flex items-start justify-between">
            <div>
              <h3 className="text-base font-bold text-gray-900">Price History</h3>
              <div className="mt-3 flex items-center gap-1">
                {["1D", "7D", "1M", "6M", "1Y", "5Y"].map((r) => (
                  <Pill key={r} active={range === r} onClick={() => setRange(r)}>
                    {r}
                  </Pill>
                ))}
              </div>
              <div className="mt-2 flex items-center gap-2 text-xs text-gray-400">
                <span>Interval:</span>
                {["15m", "30m", "1h"].map((iv) => (
                  <button
                    key={iv}
                    onClick={() => setIntervalSel(iv)}
                    className={`rounded px-2 py-0.5 ${
                      interval === iv ? "bg-gray-100 font-semibold text-gray-700" : "hover:text-gray-600"
                    }`}
                  >
                    {iv}
                  </button>
                ))}
              </div>
              <div className="mt-2 text-xs text-gray-400">Fri, 18 Sept 2026</div>
            </div>
            <div className="text-right">
              <div className="text-2xl font-bold text-gray-900">PKR 8.60</div>
              <div className="mt-1 text-sm font-semibold text-emerald-600">+1.00 (+13.16%)</div>
            </div>
          </div>

          <div className="mt-6 h-72 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={INTRADAY} margin={{ left: -12, right: 8, top: 4, bottom: 0 }}>
                <defs>
                  <linearGradient id="priceFill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#10b981" stopOpacity={0.25} />
                    <stop offset="100%" stopColor="#10b981" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid vertical={false} stroke="#f1f5f9" />
                <XAxis
                  dataKey="t"
                  tick={{ fontSize: 11, fill: "#9ca3af" }}
                  axisLine={false}
                  tickLine={false}
                  interval={2}
                />
                <YAxis
                  yAxisId="price"
                  domain={[7.1, 8.75]}
                  orientation="right"
                  tick={{ fontSize: 11, fill: "#9ca3af" }}
                  axisLine={false}
                  tickLine={false}
                  ticks={[7.2, 7.4, 7.6, 7.8, 8.0, 8.2, 8.4, 8.6]}
                />
                <YAxis yAxisId="vol" domain={[0, 16]} hide />
                <Tooltip
                  formatter={(v, name) => (name === "price" ? [v, "Price"] : [v, "Volume"])}
                  labelFormatter={(l) => l}
                />
                <Bar yAxisId="vol" dataKey="vol" barSize={10}>
                  {INTRADAY.map((d, i) => (
                    <Cell key={i} fill={d.down ? "#fca5a5" : "#a7f3d0"} />
                  ))}
                </Bar>
                <Area
                  yAxisId="price"
                  type="monotone"
                  dataKey="price"
                  stroke="#10b981"
                  strokeWidth={2}
                  fill="url(#priceFill)"
                />
              </ComposedChart>
            </ResponsiveContainer>
          </div>

          {/* Key metrics footer */}
          <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-gray-100 pt-4">
            <div className="flex flex-wrap items-center gap-4 text-xs text-gray-500">
              {KEY_METRICS.map((m) => (
                <span key={m.label} className="flex items-center gap-1.5">
                  {m.hasScore ? (
                    <span className="font-semibold text-gray-700">{m.label}</span>
                  ) : (
                    <span>{m.label}</span>
                  )}
                  <Dots score={m.score} />
                </span>
              ))}
            </div>
            <div className="flex items-center gap-1 rounded-lg bg-gray-100 p-0.5">
              {["Annual", "TTM"].map((m) => (
                <button
                  key={m}
                  onClick={() => setPerfMode(m)}
                  className={`rounded-md px-3 py-1 text-xs font-semibold ${
                    perfMode === m ? "bg-white text-gray-900 shadow-sm" : "text-gray-500"
                  }`}
                >
                  {m}
                </button>
              ))}
            </div>
          </div>
        </SectionCard>

        {/* Sidebar */}
        <SectionCard>
          <dl className="divide-y divide-gray-100 text-sm">
            <div className="flex items-center justify-between py-3 first:pt-0">
              <dt className="text-gray-500">Prev Close</dt>
              <dd className="font-semibold text-gray-900">{SIDEBAR_STATS.prevClose}</dd>
            </div>
            <div className="flex items-center justify-between py-3">
              <dt className="text-gray-500">Open</dt>
              <dd className="font-semibold text-gray-900">{SIDEBAR_STATS.open}</dd>
            </div>
            <div className="flex items-center justify-between py-3">
              <dt className="text-gray-500">Day Change</dt>
              <dd className="flex items-center gap-2">
                <span className="font-semibold text-emerald-600">{SIDEBAR_STATS.dayChange}</span>
                <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-xs font-semibold text-emerald-600">
                  {SIDEBAR_STATS.dayChangePct}
                </span>
              </dd>
            </div>
            <div className="flex items-center justify-between py-3">
              <dt className="text-gray-500">Volume</dt>
              <dd className="font-semibold text-gray-900">{SIDEBAR_STATS.volume}</dd>
            </div>
            <div className="flex items-center justify-between py-3 last:pb-0">
              <dt className="text-gray-500">YTD Return</dt>
              <dd className="font-semibold text-emerald-600">{SIDEBAR_STATS.ytdReturn}</dd>
            </div>
          </dl>

          <div className="mt-6 border-t border-gray-100 pt-5">
            <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-gray-400">Day Range</div>
            <div className="flex items-center gap-3 text-xs text-gray-500">
              <span>{SIDEBAR_STATS.dayRangeLow}</span>
              <span className="h-1.5 flex-1 rounded-full bg-gradient-to-r from-red-300 via-amber-300 to-emerald-400" />
              <span>{SIDEBAR_STATS.dayRangeHigh}</span>
            </div>
          </div>
          <div className="mt-5">
            <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-gray-400">52W Range</div>
            <div className="flex items-center gap-3 text-xs text-gray-500">
              <span>{SIDEBAR_STATS.weekRangeLow}</span>
              <span className="h-1.5 flex-1 rounded-full bg-gradient-to-r from-red-300 via-amber-300 to-emerald-400" />
              <span>{SIDEBAR_STATS.weekRangeHigh}</span>
            </div>
          </div>
        </SectionCard>
      </div>

      {/* Top stat cards */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
        {TOP_STATS.map((s) => (
          <div key={s.label} className="rounded-2xl border border-gray-100 bg-white p-4">
            <div className="flex items-center gap-2 text-xs text-gray-400">
              <span>{s.label}</span>
              {s.badge && <StatBadge type={s.badgeType}>{s.badge}</StatBadge>}
            </div>
            <div className={`mt-2 text-lg font-bold ${s.valueBad ? "text-red-500" : "text-gray-900"}`}>
              {s.value}
            </div>
            <div className="mt-1 text-[11px] text-gray-400">{s.sub}</div>
          </div>
        ))}
      </div>

      {/* Financial performance */}
      <SectionCard
        title="Financial Performance"
        right={
          <div className="flex items-center gap-1 rounded-lg bg-gray-100 p-0.5">
            {["Annual", "Quarterly"].map((m) => (
              <button
                key={m}
                className={`rounded-md px-3 py-1 text-xs font-semibold ${
                  m === "Annual" ? "bg-white text-gray-900 shadow-sm" : "text-gray-500"
                }`}
              >
                {m}
              </button>
            ))}
          </div>
        }
      >
        <div className="grid grid-cols-1 gap-8 sm:grid-cols-2">
          <div>
            <div className="mb-1 text-sm font-bold text-gray-900">Total Revenue</div>
            <div className="mb-2 text-xs text-gray-400">Total revenue from business operations</div>
            <div className="h-44">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={REVENUE_CHART}>
                  <XAxis dataKey="name" tick={{ fontSize: 11, fill: "#9ca3af" }} axisLine={false} tickLine={false} />
                  <Tooltip />
                  <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                    {REVENUE_CHART.map((d, i) => (
                      <Cell key={i} fill={barColor(d.ttm)} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
          <div>
            <div className="mb-1 text-sm font-bold text-gray-900">EBITDA</div>
            <div className="mb-2 text-xs text-gray-400">Earnings before interest, taxes, depreciation &amp; amortization</div>
            <div className="h-44">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={EBITDA_CHART}>
                  <XAxis dataKey="name" tick={{ fontSize: 11, fill: "#9ca3af" }} axisLine={false} tickLine={false} />
                  <Tooltip />
                  <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                    {EBITDA_CHART.map((d, i) => (
                      <Cell key={i} fill={barColor(d.ttm)} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
          <div>
            <div className="mb-1 text-sm font-bold text-gray-900">Net Income</div>
            <div className="mb-2 text-xs text-gray-400">Profit after all expenses and taxes</div>
            <div className="h-44">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={NET_INCOME_CHART}>
                  <XAxis dataKey="name" tick={{ fontSize: 11, fill: "#9ca3af" }} axisLine={false} tickLine={false} />
                  <Tooltip />
                  <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                    {NET_INCOME_CHART.map((d, i) => (
                      <Cell key={i} fill={barColor(d.ttm)} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
          <div>
            <div className="mb-1 text-sm font-bold text-gray-900">Earnings &amp; Dividends</div>
            <div className="mb-2 text-xs text-gray-400">EPS vs DPS per share, with payout ratio overlay</div>
            <div className="h-44">
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={EARNINGS_DIVIDENDS_CHART}>
                  <XAxis dataKey="name" tick={{ fontSize: 11, fill: "#9ca3af" }} axisLine={false} tickLine={false} />
                  <Tooltip />
                  <Bar dataKey="eps" radius={[4, 4, 0, 0]}>
                    {EARNINGS_DIVIDENDS_CHART.map((d, i) => (
                      <Cell key={i} fill={barColor(d.ttm)} />
                    ))}
                  </Bar>
                  <Line type="monotone" dataKey="payout" stroke="#f59e0b" strokeWidth={2} dot={{ r: 3 }} />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
        <p className="mt-6 text-sm leading-relaxed text-gray-500">
          Media Times Limited has shown positive revenue growth of 128.4% over the past year. Net income
          has grown by 66.7% year-over-year. The company maintains a return on equity of -6.3%.
        </p>
      </SectionCard>

      {/* Company profile */}
      <SectionCard>
        <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-gray-400">Company Profile</div>
        <h3 className="text-lg font-bold text-gray-900">About {COMPANY.name}</h3>
        <div className="mt-1 text-xs text-gray-400">
          {COMPANY.symbol} · {COMPANY.sector}
        </div>
        <p className="mt-4 max-w-3xl text-sm leading-relaxed text-gray-600">{COMPANY_PROFILE.about}</p>

        <div className="mt-6 grid grid-cols-1 gap-8 lg:grid-cols-2">
          <div>
            <h4 className="mb-2 text-sm font-bold text-gray-900">Company Information</h4>
            <dl className="divide-y divide-gray-100 rounded-xl border border-gray-100">
              {COMPANY_PROFILE.info.map((row) => (
                <div key={row.label} className="grid grid-cols-[130px_1fr] gap-4 px-4 py-3 text-sm">
                  <dt className="text-gray-400">{row.label}</dt>
                  <dd className={row.link ? "text-emerald-600" : "text-gray-800"}>{row.value}</dd>
                </div>
              ))}
            </dl>
          </div>
          <div>
            <h4 className="mb-2 text-sm font-bold text-gray-900">Key People</h4>
            <div className="divide-y divide-gray-100 rounded-xl border border-gray-100">
              {COMPANY_PROFILE.people.map((p) => (
                <div key={p.name} className="flex items-center justify-between px-4 py-3 text-sm">
                  <span className="font-semibold text-gray-900">{p.name}</span>
                  <span className="text-gray-400">{p.role}</span>
                </div>
              ))}
            </div>
            <h4 className="mb-2 mt-5 text-sm font-bold text-gray-900">Share Structure</h4>
            <dl className="divide-y divide-gray-100 rounded-xl border border-gray-100">
              <div className="flex items-center justify-between px-4 py-3 text-sm">
                <dt className="text-gray-400">Total Shares</dt>
                <dd className="font-semibold text-gray-900">{COMPANY_PROFILE.shares.total}</dd>
              </div>
              <div className="flex items-center justify-between px-4 py-3 text-sm">
                <dt className="text-gray-400">Free Float</dt>
                <dd className="font-semibold text-gray-900">
                  {COMPANY_PROFILE.shares.freeFloat}{" "}
                  <span className="font-normal text-gray-400">({COMPANY_PROFILE.shares.freeFloatPct})</span>
                </dd>
              </div>
            </dl>
          </div>
        </div>
      </SectionCard>

      <p className="text-center text-xs text-gray-400">
        {COMPANY.symbol} stock data provided by Ticker Analysts. Prices may be delayed. Data is for informational purposes only.
      </p>
    </div>
  );
}

/* ============================== generic financial table ============================== */

function FinancialTable({ sections }) {
  return (
    <SectionCard
      right={
        <div className="flex items-center gap-1 rounded-lg border border-gray-200 px-3 py-1.5 text-xs font-medium text-gray-600">
          Annual
        </div>
      }
    >
      <div className="overflow-x-auto">
        <table className="w-full min-w-[900px] border-collapse text-sm">
          <thead>
            <tr className="border-b border-gray-100 text-left text-gray-500">
              <th className="w-48 py-3 pr-4 font-semibold text-gray-700">Financial Year</th>
              {YEARS8.map((y) => (
                <th key={y} className="min-w-[100px] py-3 pr-4 text-right font-semibold text-gray-700">
                  {y}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sections.map((section) => (
              <React.Fragment key={section.title}>
                <tr className="bg-gray-50">
                  <td colSpan={YEARS8.length + 1} className="px-0 py-2 text-xs font-bold uppercase tracking-wide text-gray-500">
                    {section.title}
                  </td>
                </tr>
                {section.rows.map((r) => (
                  <tr key={r.label} className="border-b border-gray-50">
                    <td className="py-3 pr-4 text-gray-700">{r.label}</td>
                    {r.values.map((cell, i) => (
                      <td key={i} className="py-3 pr-4 text-right">
                        <div className="font-medium text-gray-900">{cell.v}</div>
                        <ChangeText pos={cell.pos}>{cell.yoy}</ChangeText>
                      </td>
                    ))}
                  </tr>
                ))}
              </React.Fragment>
            ))}
          </tbody>
        </table>
      </div>
    </SectionCard>
  );
}

/* =================================== Technicals tab =================================== */

function TechnicalsTab() {
  return (
    <div className="space-y-6">
      <SectionCard>
        <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-gray-400">Technical Summary</div>
        <p className="mb-6 text-sm text-gray-500">
          Aggregated signal from <span className="font-semibold text-gray-700">23 indicators</span> · 18 Sept 2026
        </p>
        <div className="grid grid-cols-1 gap-6 sm:grid-cols-3">
          <Gauge value={0.5} label="Oscillators" sublabel="Neutral" sell={4} neutral={3} buy={4} />
          <Gauge value={0.72} label="Summary" sublabel="Buy" sell={4} neutral={3} buy={16} />
          <Gauge value={0.96} label="Moving Averages" sublabel="Strong Buy" sell={0} neutral={0} buy={12} />
        </div>
      </SectionCard>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <SectionCard
          title="Oscillators"
          right={<span className="text-xs text-gray-400">11 indicators</span>}
        >
          <div className="divide-y divide-gray-50">
            {OSCILLATORS.map((o) => (
              <div key={o.label} className="flex items-center justify-between py-3 text-sm">
                <span className="text-gray-600">{o.label}</span>
                <div className="flex items-center gap-3">
                  <span className="text-gray-900">{o.value}</span>
                  <SignalBadge signal={o.signal} />
                </div>
              </div>
            ))}
          </div>
        </SectionCard>

        <SectionCard
          title="Moving Averages"
          right={<span className="text-xs text-gray-400">12 indicators</span>}
        >
          <div className="divide-y divide-gray-50">
            {MOVING_AVERAGES.map((m) => (
              <div key={m.label} className="flex items-center justify-between py-3 text-sm">
                <span className="text-gray-600">{m.label}</span>
                <div className="flex items-center gap-3">
                  <span className="text-gray-900">
                    {m.value} <span className="text-emerald-600">({m.pct})</span>
                  </span>
                  <SignalBadge signal={m.signal} />
                </div>
              </div>
            ))}
          </div>
        </SectionCard>
      </div>
    </div>
  );
}

/* =================================== Ratios tab =================================== */

function MetricGrid({ metrics }) {
  return (
    <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
      {metrics.map((m) => (
        <div key={m.label} className="rounded-xl border border-gray-100 p-4">
          <div className="text-[11px] font-semibold uppercase tracking-wide text-gray-400">{m.label}</div>
          <div
            className={`mt-2 text-lg font-bold ${
              m.bad ? "text-red-500" : m.good ? "text-emerald-600" : "text-gray-900"
            }`}
          >
            {m.value}
          </div>
          <div className="mt-1 text-[11px] text-gray-400">{m.sub}</div>
        </div>
      ))}
    </div>
  );
}

function RatiosTab() {
  return (
    <div className="space-y-6">
      <SectionCard>
        <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-gray-400">Valuation</div>
        <p className="mb-4 text-sm text-gray-500">How the market prices the business</p>
        <MetricGrid metrics={VALUATION_METRICS} />
      </SectionCard>
      <SectionCard>
        <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-gray-400">Profitability</div>
        <p className="mb-4 text-sm text-gray-500">How efficiently the business turns revenue into profit</p>
        <MetricGrid metrics={PROFITABILITY_METRICS} />
      </SectionCard>
    </div>
  );
}

/* =================================== Peers tab =================================== */

const PEER_COLS = [
  { key: "revenue", label: "Revenue FY" },
  { key: "revGrowth", label: "Rev Growth YoY" },
  { key: "profit", label: "Profit FY" },
  { key: "profitGrowth", label: "Profit Growth YoY" },
  { key: "eps", label: "EPS FY" },
  { key: "epsGrowth", label: "EPS Growth YoY" },
  { key: "pe", label: "P/E" },
  { key: "divYield", label: "Div Yield" },
  { key: "ytd", label: "YTD Return" },
];

function PeersTab() {
  return (
    <SectionCard
      right={
        <div className="flex items-center gap-1 rounded-lg bg-gray-100 p-0.5">
          {["Annual", "TTM"].map((m) => (
            <button
              key={m}
              className={`rounded-md px-3 py-1 text-xs font-semibold ${
                m === "Annual" ? "bg-white text-gray-900 shadow-sm" : "text-gray-500"
              }`}
            >
              {m}
            </button>
          ))}
        </div>
      }
    >
      <h3 className="text-base font-bold text-gray-900">Sector Peers</h3>
      <p className="mb-4 text-sm text-gray-500">Top 10 peers in {COMPANY.sector} by market cap · latest FY</p>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[1100px] border-collapse text-sm">
          <thead>
            <tr className="border-b border-gray-100 text-left text-gray-500">
              <th className="py-3 pr-4 font-semibold">Company</th>
              {PEER_COLS.map((c) => (
                <th key={c.key} className="py-3 pr-4 text-right font-semibold">
                  {c.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {PEERS.map((p) => (
              <tr key={p.symbol} className={`border-b border-gray-50 ${p.current ? "bg-amber-50" : ""}`}>
                <td className="py-3 pr-4">
                  <div className="font-bold text-gray-900">{p.symbol}</div>
                  <div className="text-xs text-gray-400">{p.name}</div>
                </td>
                {PEER_COLS.map((c) => {
                  const v = p[c.key];
                  const isPct = typeof v === "string" && (v.includes("%"));
                  const isNeg = typeof v === "string" && v.trim().startsWith("-");
                  return (
                    <td
                      key={c.key}
                      className={`py-3 pr-4 text-right ${
                        isPct ? (isNeg ? "text-red-500" : v === "—" ? "text-gray-400" : "text-emerald-600") : "text-gray-800"
                      }`}
                    >
                      {v}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </SectionCard>
  );
}

/* =================================== Activities tab =================================== */

function ActivitiesTab() {
  const [search, setSearch] = useState("");
  const [priority, setPriority] = useState(null);

  const rows = ACTIVITIES.filter((a) => a.title.toLowerCase().includes(search.toLowerCase()));

  return (
    <SectionCard>
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex w-full max-w-sm items-center gap-2 rounded-lg border border-gray-200 px-3 py-2">
          <Search className="h-4 w-4 text-gray-400" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search activities"
            className="w-full bg-transparent text-sm text-gray-700 outline-none placeholder:text-gray-400"
          />
        </div>
        <div className="flex items-center gap-3 text-xs">
          <span className="font-semibold uppercase tracking-wide text-gray-400">Priority</span>
          {["Critical", "High", "Medium"].map((p) => (
            <button
              key={p}
              onClick={() => setPriority(priority === p ? null : p)}
              className={`font-medium ${priority === p ? "text-emerald-600" : "text-gray-500 hover:text-gray-700"}`}
            >
              {p}
            </button>
          ))}
        </div>
      </div>

      <div className="mt-4 divide-y divide-gray-100">
        {rows.map((a, i) => (
          <div key={i} className="flex items-start justify-between gap-4 py-4">
            <div className="flex items-start gap-3">
              <span className="relative flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-emerald-50 text-emerald-700">
                ▲
              </span>
              <div>
                <div className="flex items-center gap-2 text-xs">
                  <span className="font-bold text-gray-900">{COMPANY.symbol}</span>
                  {a.tags.map((t) => (
                    <span
                      key={t}
                      className={
                        t === "Exchange Notice"
                          ? "text-blue-500"
                          : "rounded bg-amber-50 px-1.5 py-0.5 font-semibold text-amber-600"
                      }
                    >
                      {t}
                    </span>
                  ))}
                </div>
                <div className="mt-1 text-sm font-medium text-gray-800">{a.title}</div>
                <a href="#" className="mt-1 inline-flex items-center gap-1 text-xs text-blue-500 hover:underline">
                  Source <ExternalLink className="h-3 w-3" />
                </a>
              </div>
            </div>
            <span className="shrink-0 text-xs text-gray-400">{a.date}</span>
          </div>
        ))}
        {rows.length === 0 && (
          <div className="py-10 text-center text-sm text-gray-400">No activities match your search.</div>
        )}
      </div>
    </SectionCard>
  );
}

/* ======================================== App ======================================== */

// recharts <Cell> is used inside Bar for per-bar colors; import it directly
// here to keep the single-file structure simple.
import { Cell } from "recharts";

export default function StockDetailPage() {
  const [tab, setTab] = useState("Overview");

  return (
    <div className="min-h-screen w-full bg-gray-50" style={{ fontFamily: FONT_STACK }}>
      <link rel="preconnect" href="https://fonts.googleapis.com" />
      <link
        href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap"
        rel="stylesheet"
      />

      {/* Header */}
      <div className="border-b border-gray-100 bg-white px-6 py-6">
        <div className="mx-auto flex max-w-6xl items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-emerald-50 text-2xl text-emerald-600">
              ▲
            </div>
            <div>
              <h1 className="text-2xl font-bold text-gray-900">{COMPANY.name}</h1>
              <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-gray-400">
                <span className="rounded bg-gray-100 px-1.5 py-0.5 font-semibold text-gray-600">
                  {COMPANY.symbol}
                </span>
                <span>{COMPANY.sector}</span>
                <span>·</span>
                <span>{COMPANY.rank}</span>
                <span>·</span>
                <a href="#" className="flex items-center gap-1 font-medium text-emerald-600 hover:underline">
                  Open in DPS PSX <ExternalLink className="h-3 w-3" />
                </a>
              </div>
            </div>
          </div>
          <button className="rounded-full bg-emerald-500 px-5 py-2.5 text-sm font-semibold text-white hover:bg-emerald-600">
            Buy {COMPANY.symbol}
          </button>
        </div>

        {/* Tabs */}
        <div className="mx-auto mt-5 flex max-w-6xl items-center gap-6 overflow-x-auto text-sm">
          {TABS.map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`shrink-0 border-b-2 pb-2 font-medium transition ${
                tab === t ? "border-gray-900 text-gray-900" : "border-transparent text-gray-400 hover:text-gray-600"
              }`}
            >
              {t}
            </button>
          ))}
        </div>
      </div>

      {/* Content */}
      <div className="mx-auto max-w-6xl px-6 py-8">
        {tab === "Overview" && <OverviewTab />}
        {tab === "Income Statement" && <FinancialTable sections={INCOME_STATEMENT} />}
        {tab === "Balance Sheet" && <FinancialTable sections={BALANCE_SHEET} />}
        {tab === "Cash Flow" && <FinancialTable sections={CASH_FLOW} />}
        {tab === "Technicals" && <TechnicalsTab />}
        {tab === "Ratios" && <RatiosTab />}
        {tab === "Peers" && <PeersTab />}
        {tab === "Activities" && <ActivitiesTab />}
      </div>
    </div>
  );
}