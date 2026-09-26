import React, { useState } from 'react'
import { formatNumber, formatMoney, formatCompactNumber, formatPercent, formatDate } from '../utils/formatters'

export default function StockFundamentals({
  symbol,
  fundamentals,
  overview,
}) {
  const [subSection, setSubSection] = useState('ratios')

  if (!fundamentals) {
    return (
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-8 text-center">
        <p className="text-slate-400 text-sm">Fundamental financial data is loading for {symbol}...</p>
      </div>
    )
  }

  const {
    company_profile = {},
    equity_profile = {},
    ratios = {},
    trading_limits = {},
    dividend_history = [],
    announcements = [],
    metrics = [],
    financials_annual = [],
    financials_quarterly = [],
  } = fundamentals

  const hasAnnual = Array.isArray(financials_annual) && financials_annual.length > 0
  const hasQuarterly = Array.isArray(financials_quarterly) && financials_quarterly.length > 0
  const hasDividends = Array.isArray(dividend_history) && dividend_history.length > 0
  const hasAnnouncements = Array.isArray(announcements) && announcements.length > 0
  const hasMetrics = Array.isArray(metrics) && metrics.length > 0

  return (
    <div className="space-y-6">
      {/* Sub-navigation pills */}
      <div className="flex items-center gap-2 overflow-x-auto pb-1 border-b border-slate-100 dark:border-slate-800">
        {[
          ['ratios', 'Ratios & Valuation'],
          ['profile', 'Company Profile & Governance'],
          ['equity', 'Capital & Trading Limits'],
          ['dividends', `Dividend History (${hasDividends ? dividend_history.length : 0})`],
          ['announcements', `Announcements & Filings (${hasAnnouncements ? announcements.length : 0})`],
          ['financials', 'Financial Statements'],
        ].map(([key, label]) => (
          <button
            key={key}
            type="button"
            onClick={() => setSubSection(key)}
            className={`px-3 py-1.5 text-xs font-semibold rounded-lg whitespace-nowrap transition-all ${
              subSection === key
                ? 'bg-emerald-600 text-white shadow-xs'
                : 'bg-slate-100 text-slate-600 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* 1. Ratios & Valuation */}
      {subSection === 'ratios' && (
        <div className="space-y-6">
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
            <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-4 shadow-xs">
              <span className="text-xs text-slate-500 dark:text-slate-400 font-medium">P/E Ratio (TTM)</span>
              <div className="text-xl font-bold font-mono text-slate-900 dark:text-slate-100 mt-1">
                {formatNumber(ratios.pe_ratio ?? overview?.pe_ratio)}
              </div>
              <span className="text-[11px] text-slate-400">Price to Earnings</span>
            </div>

            <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-4 shadow-xs">
              <span className="text-xs text-slate-500 dark:text-slate-400 font-medium">PEG Ratio</span>
              <div className="text-xl font-bold font-mono text-slate-900 dark:text-slate-100 mt-1">
                {formatNumber(ratios.peg_ratio)}
              </div>
              <span className="text-[11px] text-slate-400">P/E to Growth</span>
            </div>

            <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-4 shadow-xs">
              <span className="text-xs text-slate-500 dark:text-slate-400 font-medium">Earnings Per Share (EPS)</span>
              <div className="text-xl font-bold font-mono text-slate-900 dark:text-slate-100 mt-1">
                PKR {formatNumber(ratios.eps)}
              </div>
              <span className="text-[11px] text-slate-400">Trailing 12 Months</span>
            </div>

            <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-4 shadow-xs">
              <span className="text-xs text-slate-500 dark:text-slate-400 font-medium">EPS Growth (YoY)</span>
              <div className={`text-xl font-bold font-mono mt-1 ${Number(ratios.eps_growth_pct) >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400'}`}>
                {formatPercent(ratios.eps_growth_pct)}
              </div>
              <span className="text-[11px] text-slate-400">Year over Year</span>
            </div>

            <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-4 shadow-xs">
              <span className="text-xs text-slate-500 dark:text-slate-400 font-medium">Dividend Yield</span>
              <div className="text-xl font-bold font-mono text-emerald-600 dark:text-emerald-400 mt-1">
                {formatPercent(ratios.dividend_yield_pct)}
              </div>
              <span className="text-[11px] text-slate-400">Annualized Cash Yield</span>
            </div>

            <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-4 shadow-xs">
              <span className="text-xs text-slate-500 dark:text-slate-400 font-medium">Net Profit Margin</span>
              <div className="text-xl font-bold font-mono text-slate-900 dark:text-slate-100 mt-1">
                {formatPercent(ratios.net_profit_margin_pct)}
              </div>
              <span className="text-[11px] text-slate-400">Net Income / Revenue</span>
            </div>

            <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-4 shadow-xs">
              <span className="text-xs text-slate-500 dark:text-slate-400 font-medium">Gross Profit Margin</span>
              <div className="text-xl font-bold font-mono text-slate-900 dark:text-slate-100 mt-1">
                {formatPercent(ratios.gross_profit_margin_pct)}
              </div>
              <span className="text-[11px] text-slate-400">Gross Margin</span>
            </div>

            <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-4 shadow-xs">
              <span className="text-xs text-slate-500 dark:text-slate-400 font-medium">Free Float %</span>
              <div className="text-xl font-bold font-mono text-slate-900 dark:text-slate-100 mt-1">
                {formatPercent(equity_profile.free_float_pct)}
              </div>
              <span className="text-[11px] text-slate-400">Tradable Liquidity</span>
            </div>
          </div>

          {/* Dynamic Extra Metrics if present */}
          {hasMetrics && (
            <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-xs">
              <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100 mb-4">
                Additional Quantitative Metrics
              </h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                {metrics.map((m, idx) => (
                  <div key={idx} className="p-3 bg-slate-50 dark:bg-slate-800/50 rounded-xl border border-slate-100 dark:border-slate-800">
                    <span className="text-xs text-slate-500 block">{m.key}</span>
                    <strong className="text-sm font-mono text-slate-900 dark:text-slate-100">{m.value}</strong>
                    {m.note && <span className="text-[11px] text-slate-400 block mt-0.5">{m.note}</span>}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* 2. Company Profile & Governance */}
      {subSection === 'profile' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-xs space-y-4">
            <div>
              <h3 className="text-base font-bold text-slate-900 dark:text-slate-100">
                Business Description
              </h3>
              <p className="text-sm text-slate-600 dark:text-slate-300 leading-relaxed mt-2 whitespace-pre-line">
                {company_profile.business_description ||
                  `${company_profile.name || overview?.name || symbol} is an established company listed on the Pakistan Stock Exchange operating in the ${overview?.sector || 'commercial'} sector.`}
              </p>
            </div>

            <div className="pt-4 border-t border-slate-100 dark:border-slate-800">
              <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-3">
                Registered Head Office
              </h4>
              <p className="text-sm text-slate-700 dark:text-slate-300 font-mono">
                {company_profile.address || 'Karachi, Pakistan'}
              </p>
            </div>
          </div>

          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-xs space-y-4">
            <h3 className="text-base font-bold text-slate-900 dark:text-slate-100">
              Executive Governance
            </h3>
            <div className="space-y-3 divide-y divide-slate-100 dark:divide-slate-800">
              <div className="pt-2">
                <span className="text-xs text-slate-400 block">Chief Executive Officer (CEO)</span>
                <strong className="text-sm text-slate-800 dark:text-slate-200">{company_profile.ceo || '—'}</strong>
              </div>
              <div className="pt-3">
                <span className="text-xs text-slate-400 block">Chairperson</span>
                <strong className="text-sm text-slate-800 dark:text-slate-200">{company_profile.chairperson || '—'}</strong>
              </div>
              <div className="pt-3">
                <span className="text-xs text-slate-400 block">Company Secretary</span>
                <strong className="text-sm text-slate-800 dark:text-slate-200">
                  {company_profile.company_secretary || company_profile.secretary || '—'}
                </strong>
              </div>
              <div className="pt-3">
                <span className="text-xs text-slate-400 block">Official Investor Website</span>
                {company_profile.website ? (
                  <a
                    href={company_profile.website.startsWith('http') ? company_profile.website : `https://${company_profile.website}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs font-semibold text-emerald-600 dark:text-emerald-400 hover:underline flex items-center gap-1 mt-1 truncate"
                  >
                    <span>{company_profile.website}</span>
                    <span>↗</span>
                  </a>
                ) : (
                  <span className="text-sm text-slate-400">—</span>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 3. Equity Profile & Trading Limits */}
      {subSection === 'equity' && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Equity Profile */}
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-xs space-y-4">
            <h3 className="text-base font-bold text-slate-900 dark:text-slate-100">
              Capital Structure &amp; Float
            </h3>
            <div className="divide-y divide-slate-100 dark:divide-slate-800 space-y-3">
              <div className="flex items-center justify-between pt-1">
                <span className="text-sm text-slate-500 dark:text-slate-400">Market Capitalization</span>
                <strong className="text-sm font-mono text-slate-900 dark:text-slate-100">
                  {formatMoney(equity_profile.market_cap_pkr ?? overview?.market_cap)}
                </strong>
              </div>
              <div className="flex items-center justify-between pt-3">
                <span className="text-sm text-slate-500 dark:text-slate-400">Total Shares Outstanding</span>
                <strong className="text-sm font-mono text-slate-900 dark:text-slate-100">
                  {formatCompactNumber(equity_profile.total_shares)}
                </strong>
              </div>
              <div className="flex items-center justify-between pt-3">
                <span className="text-sm text-slate-500 dark:text-slate-400">Free Float Shares</span>
                <strong className="text-sm font-mono text-slate-900 dark:text-slate-100">
                  {formatCompactNumber(equity_profile.free_float_shares)}
                </strong>
              </div>
              <div className="flex items-center justify-between pt-3">
                <span className="text-sm text-slate-500 dark:text-slate-400">Free Float Percentage</span>
                <strong className="text-sm font-mono text-emerald-600 dark:text-emerald-400">
                  {formatPercent(equity_profile.free_float_pct)}
                </strong>
              </div>
            </div>
          </div>

          {/* Trading Limits & Price Boundaries */}
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-xs space-y-4">
            <h3 className="text-base font-bold text-slate-900 dark:text-slate-100">
              PSX Trading Limits &amp; Boundaries
            </h3>
            <div className="divide-y divide-slate-100 dark:divide-slate-800 space-y-3">
              <div className="flex items-center justify-between pt-1">
                <span className="text-sm text-slate-500 dark:text-slate-400">52-Week High</span>
                <strong className="text-sm font-mono text-emerald-600 dark:text-emerald-400">
                  PKR {formatNumber(trading_limits.year_high)}
                </strong>
              </div>
              <div className="flex items-center justify-between pt-3">
                <span className="text-sm text-slate-500 dark:text-slate-400">52-Week Low</span>
                <strong className="text-sm font-mono text-rose-600 dark:text-rose-400">
                  PKR {formatNumber(trading_limits.year_low)}
                </strong>
              </div>
              <div className="flex items-center justify-between pt-3">
                <span className="text-sm text-slate-500 dark:text-slate-400">Lower Circuit Breaker</span>
                <strong className="text-sm font-mono text-rose-500">
                  PKR {formatNumber(trading_limits.circuit_breaker_lower)}
                </strong>
              </div>
              <div className="flex items-center justify-between pt-3">
                <span className="text-sm text-slate-500 dark:text-slate-400">Upper Circuit Breaker</span>
                <strong className="text-sm font-mono text-emerald-500">
                  PKR {formatNumber(trading_limits.circuit_breaker_upper)}
                </strong>
              </div>
              <div className="flex items-center justify-between pt-3">
                <span className="text-sm text-slate-500 dark:text-slate-400">1-Year Change</span>
                <strong className={`text-sm font-mono ${Number(trading_limits.year_change_pct) >= 0 ? 'text-emerald-600' : 'text-rose-600'}`}>
                  {formatPercent(trading_limits.year_change_pct)}
                </strong>
              </div>
              <div className="flex items-center justify-between pt-3">
                <span className="text-sm text-slate-500 dark:text-slate-400">YTD Change</span>
                <strong className={`text-sm font-mono ${Number(trading_limits.ytd_change_pct) >= 0 ? 'text-emerald-600' : 'text-rose-600'}`}>
                  {formatPercent(trading_limits.ytd_change_pct)}
                </strong>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 4. Dividend History Table */}
      {subSection === 'dividends' && (
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-xs">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-base font-bold text-slate-900 dark:text-slate-100">
                Corporate Dividend Distributions
              </h3>
              <p className="text-xs text-slate-500">Historical cash payouts and entitlement dates</p>
            </div>
            {hasDividends && (
              <span className="text-xs font-semibold px-2.5 py-1 rounded-full bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300">
                {dividend_history.length} Record(s)
              </span>
            )}
          </div>

          {!hasDividends ? (
            <div className="py-8 text-center text-slate-400 text-xs">
              No historical cash dividend payouts recorded for {symbol}.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-slate-200 dark:border-slate-800 text-slate-400 uppercase tracking-wider font-semibold">
                    <th className="py-2.5 px-3">Ex-Date</th>
                    <th className="py-2.5 px-3">Cash Amount</th>
                    <th className="py-2.5 px-3">Record Date</th>
                    <th className="py-2.5 px-3">Payment Date</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800 font-mono">
                  {dividend_history.map((div, i) => (
                    <tr key={i} className="hover:bg-slate-50 dark:hover:bg-slate-800/40">
                      <td className="py-3 px-3 font-semibold text-slate-800 dark:text-slate-200">
                        {formatDate(div.ex_date)}
                      </td>
                      <td className="py-3 px-3 text-emerald-600 dark:text-emerald-400 font-bold">
                        PKR {formatNumber(div.cash_amount)}
                      </td>
                      <td className="py-3 px-3 text-slate-500">
                        {formatDate(div.record_date)}
                      </td>
                      <td className="py-3 px-3 text-slate-500">
                        {formatDate(div.pay_date)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* 5. Company Announcements & Disclosures */}
      {subSection === 'announcements' && (
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-xs">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-base font-bold text-slate-900 dark:text-slate-100">
                Official PSX Disclosures &amp; Filings
              </h3>
              <p className="text-xs text-slate-500">Material information, financial results, and board decisions</p>
            </div>
            {hasAnnouncements && (
              <span className="text-xs font-semibold px-2.5 py-1 rounded-full bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300">
                {announcements.length} Document(s)
              </span>
            )}
          </div>

          {!hasAnnouncements ? (
            <div className="py-8 text-center text-slate-400 text-xs">
              No recent official announcements recorded for {symbol}.
            </div>
          ) : (
            <div className="space-y-3">
              {announcements.map((ann, i) => (
                <div
                  key={i}
                  className="p-4 rounded-xl border border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/30 flex items-start justify-between gap-4"
                >
                  <div className="space-y-1">
                    <span className="text-[11px] font-mono text-slate-400 font-medium">
                      {formatDate(ann.date)}
                    </span>
                    <h4 className="text-sm font-semibold text-slate-900 dark:text-slate-100 leading-snug m-0">
                      {ann.title}
                    </h4>
                  </div>
                  {ann.pdf_link && (
                    <a
                      href={ann.pdf_link}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="shrink-0 px-3 py-1.5 rounded-lg bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-300 hover:bg-emerald-100 dark:hover:bg-emerald-900/50 text-xs font-semibold flex items-center gap-1.5 transition-colors border border-emerald-200 dark:border-emerald-800"
                    >
                      <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                      </svg>
                      <span>PDF Document</span>
                    </a>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* 6. Financial Statements */}
      {subSection === 'financials' && (
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-xs">
          <h3 className="text-base font-bold text-slate-900 dark:text-slate-100 mb-2">
            Annual &amp; Quarterly Statements
          </h3>
          {hasAnnual || hasQuarterly ? (
            <div className="space-y-6">
              {hasAnnual && (
                <div>
                  <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-2">
                    Annual Financial Statements (Audited)
                  </h4>
                  <div className="overflow-x-auto border border-slate-200 dark:border-slate-800 rounded-xl">
                    <table className="w-full text-left text-xs">
                      <thead>
                        <tr className="bg-slate-50 dark:bg-slate-800/60 border-b border-slate-200 dark:border-slate-800 text-slate-500 dark:text-slate-400 font-semibold uppercase tracking-wider">
                          <th className="py-2.5 px-3">Fiscal Year</th>
                          <th className="py-2.5 px-3">Sales / Turnover</th>
                          <th className="py-2.5 px-3">Profit After Tax (PAT)</th>
                          <th className="py-2.5 px-3">Earnings Per Share (EPS)</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100 dark:divide-slate-800 font-mono">
                        {financials_annual.map((row, idx) => (
                          <tr key={idx} className="hover:bg-slate-50/50 dark:hover:bg-slate-800/40">
                            <td className="py-2.5 px-3 font-bold text-slate-900 dark:text-slate-100">{row.period}</td>
                            <td className="py-2.5 px-3 text-slate-700 dark:text-slate-300">
                              {row.values?.sales != null ? formatMoney(row.values.sales) : '—'}
                            </td>
                            <td className={`py-2.5 px-3 font-semibold ${Number(row.values?.profit_after_tax) >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400'}`}>
                              {row.values?.profit_after_tax != null ? formatMoney(row.values.profit_after_tax) : '—'}
                            </td>
                            <td className="py-2.5 px-3 font-bold text-slate-900 dark:text-slate-100">
                              {row.values?.eps != null ? `PKR ${formatNumber(row.values.eps)}` : '—'}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
              {hasQuarterly && (
                <div>
                  <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-2">
                    Quarterly Financial Statements
                  </h4>
                  <div className="overflow-x-auto border border-slate-200 dark:border-slate-800 rounded-xl">
                    <table className="w-full text-left text-xs">
                      <thead>
                        <tr className="bg-slate-50 dark:bg-slate-800/60 border-b border-slate-200 dark:border-slate-800 text-slate-500 dark:text-slate-400 font-semibold uppercase tracking-wider">
                          <th className="py-2.5 px-3">Period</th>
                          <th className="py-2.5 px-3">Sales / Turnover</th>
                          <th className="py-2.5 px-3">Profit After Tax (PAT)</th>
                          <th className="py-2.5 px-3">Earnings Per Share (EPS)</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100 dark:divide-slate-800 font-mono">
                        {financials_quarterly.map((row, idx) => (
                          <tr key={idx} className="hover:bg-slate-50/50 dark:hover:bg-slate-800/40">
                            <td className="py-2.5 px-3 font-bold text-slate-900 dark:text-slate-100">{row.period}</td>
                            <td className="py-2.5 px-3 text-slate-700 dark:text-slate-300">
                              {row.values?.sales != null ? formatMoney(row.values.sales) : '—'}
                            </td>
                            <td className={`py-2.5 px-3 font-semibold ${Number(row.values?.profit_after_tax) >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400'}`}>
                              {row.values?.profit_after_tax != null ? formatMoney(row.values.profit_after_tax) : '—'}
                            </td>
                            <td className="py-2.5 px-3 font-bold text-slate-900 dark:text-slate-100">
                              {row.values?.eps != null ? `PKR ${formatNumber(row.values.eps)}` : '—'}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="p-6 bg-slate-50 dark:bg-slate-800/40 rounded-xl border border-slate-100 dark:border-slate-800 text-center">
              <p className="text-xs text-slate-500 dark:text-slate-400 m-0">
                Detailed balance sheet and income statement filings for {symbol} are currently being processed from PSX quarterly XBRL disclosures. Key financial ratios and valuation multiples above reflect the latest audited statements.
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

