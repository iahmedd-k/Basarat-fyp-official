import React from 'react'
import StockLogo from './StockLogo'

function formatNumber(value, fractionDigits = 2) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '0'
  return Number(value).toLocaleString('en-PK', {
    minimumFractionDigits: fractionDigits,
    maximumFractionDigits: fractionDigits,
  })
}

function formatMoney(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return 'PKR 0'
  const isNeg = Number(value) < 0
  const absVal = Math.abs(Number(value))
  return `${isNeg ? '-' : ''}PKR ${formatNumber(absVal, 0)}`
}

export default function RiskStressTable({ holdingImpacts = [], onStock }) {
  if (!holdingImpacts || holdingImpacts.length === 0) {
    return (
      <div className="py-8 text-center text-sm text-slate-500 dark:text-slate-400">
        No holding shock impacts available for this scenario.
      </div>
    )
  }

  return (
    <div className="overflow-x-auto w-full">
      <table className="w-full text-left text-xs border-collapse">
        <thead>
          <tr className="border-b border-slate-200 dark:border-slate-800 text-[11px] font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider bg-slate-50/50 dark:bg-slate-900/40">
            <th className="py-3 px-3.5">Asset</th>
            <th className="py-3 px-3.5">Sector</th>
            <th className="py-3 px-3.5 text-right">Current Value</th>
            <th className="py-3 px-3.5 text-right">Weight</th>
            <th className="py-3 px-3.5 text-right">Scenario Shock</th>
            <th className="py-3 px-3.5 text-right">Impact (PKR)</th>
            <th className="py-3 px-3.5 text-right">Stressed Value</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60 font-mono">
          {holdingImpacts.map((holding) => {
            const shock = Number(holding.shock_pct || 0)
            const isNegativeShock = shock < 0
            const impactVal = Number(holding.impact_value || 0)
            const isNegativeImpact = impactVal < 0
            const stressedVal = Number(holding.current_value || 0) + impactVal

            return (
              <tr key={holding.symbol} className="hover:bg-slate-50/80 dark:hover:bg-slate-800/40 transition-colors">
                <td className="py-3 px-3.5 font-sans">
                  <button
                    type="button"
                    onClick={() => onStock?.(holding.symbol)}
                    className="flex items-center gap-2 font-bold text-slate-800 dark:text-slate-200 hover:text-emerald-600 dark:hover:text-emerald-400 transition-colors cursor-pointer"
                  >
                    <StockLogo symbol={holding.symbol} size="xs" />
                    <span>{holding.symbol}</span>
                  </button>
                </td>
                <td className="py-3 px-3.5 text-slate-600 dark:text-slate-400 font-sans">
                  {holding.sector || 'Default'}
                </td>
                <td className="py-3 px-3.5 text-right text-slate-700 dark:text-slate-300">
                  {formatMoney(holding.current_value)}
                </td>
                <td className="py-3 px-3.5 text-right text-slate-500 dark:text-slate-400">
                  {holding.weight_pct != null ? `${Number(holding.weight_pct).toFixed(1)}%` : '—'}
                </td>
                <td className="py-3 px-3.5 text-right">
                  <span
                    className={`inline-block px-2 py-0.5 rounded text-[11px] font-semibold ${
                      isNegativeShock
                        ? 'bg-rose-50 text-rose-700 dark:bg-rose-500/10 dark:text-rose-400 border border-rose-200/80 dark:border-rose-500/20'
                        : shock > 0
                        ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-400 border border-emerald-200/80 dark:border-emerald-500/20'
                        : 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400'
                    }`}
                  >
                    {shock > 0 ? `+${shock.toFixed(1)}%` : `${shock.toFixed(1)}%`}
                  </span>
                </td>
                <td className={`py-3 px-3.5 text-right font-semibold ${isNegativeImpact ? 'text-rose-600 dark:text-rose-400' : 'text-emerald-600 dark:text-emerald-400'}`}>
                  {isNegativeImpact ? `-${formatMoney(Math.abs(impactVal))}` : `+${formatMoney(impactVal)}`}
                </td>
                <td className="py-3 px-3.5 text-right text-slate-900 dark:text-slate-200 font-bold">
                  {formatMoney(stressedVal)}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
