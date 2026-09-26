import React from 'react'

/**
 * Authentic vector Mosque Icon matching TickerAnalysts' Shariah symbol.
 * Clean, high-contrast, scalable vector rendering of minarets and dome.
 */
export function MosqueIcon({ className = 'w-3.5 h-3.5' }) {
  return (
    <svg
      fill="currentColor"
      viewBox="0 0 32 32"
      className={`shrink-0 ${className}`}
      aria-hidden="true"
    >
      <path d="M 6.4375 4.15625 L 5.53125 6.65625 L 4.0625 10.65625 L 4 10.8125 L 4 28 L 15 28 L 15 25 C 15 24.410156 15.101563 24.152344 15.1875 24 C 15.273438 23.847656 15.371094 23.757813 15.59375 23.59375 C 15.707031 23.511719 15.839844 23.417969 16 23.28125 C 16.160156 23.417969 16.292969 23.511719 16.40625 23.59375 C 16.628906 23.757813 16.726563 23.847656 16.8125 24 C 16.898438 24.152344 17 24.410156 17 25 L 17 28 L 28 28 L 28 10.8125 L 27.9375 10.625 L 26.40625 6.625 L 25.4375 4.15625 L 24.53125 6.65625 L 23.0625 10.65625 L 23 10.8125 L 23 17 L 22.90625 17 C 22.585938 14.289063 21.019531 12.636719 19.5625 11.65625 C 18.75 11.109375 17.980469 10.726563 17.5 10.40625 C 17.261719 10.246094 17.09375 10.105469 17.03125 10.03125 C 16.96875 9.957031 17 9.988281 17 10 L 17 9 L 15 9 L 15 10 C 15 9.988281 15.03125 9.953125 14.96875 10.03125 C 14.90625 10.109375 14.742188 10.273438 14.5 10.4375 C 14.019531 10.765625 13.25 11.167969 12.4375 11.71875 C 10.988281 12.703125 9.421875 14.335938 9.09375 17 L 9 17 L 9 10.8125 L 8.9375 10.625 L 7.40625 6.625 Z M 6.46875 9.875 L 7 11.21875 L 7 26 L 6 26 L 6 11.1875 Z M 25.46875 9.875 L 26 11.21875 L 26 26 L 25 26 L 25 11.1875 Z M 16 11.78125 C 16.125 11.878906 16.246094 11.976563 16.375 12.0625 C 17.019531 12.492188 17.75 12.882813 18.4375 13.34375 C 19.617188 14.140625 20.636719 15.078125 20.90625 17 L 11.09375 17 C 11.363281 15.101563 12.378906 14.148438 13.5625 13.34375 C 14.25 12.875 14.980469 12.5 15.625 12.0625 C 15.753906 11.972656 15.875 11.878906 16 11.78125 Z M 9 19 L 23 19 L 23 26 L 19 26 L 19 25 C 19 24.175781 18.851563 23.511719 18.5625 23 C 18.273438 22.488281 17.871094 22.167969 17.59375 21.96875 C 17.316406 21.769531 17.183594 21.671875 17.125 21.59375 C 17.066406 21.515625 17 21.414063 17 21 L 15 21 C 15 21.414063 14.933594 21.515625 14.875 21.59375 C 14.816406 21.671875 14.683594 21.769531 14.40625 21.96875 C 14.128906 22.167969 13.726563 22.488281 13.4375 23 C 13.148438 23.511719 13 24.175781 13 25 L 13 26 L 9 26 Z" />
    </svg>
  )
}

/**
 * Professional Shariah Compliance Indicator.
 * Renders a recognized Mosque vector icon and compliance text.
 * Strictly driven by backend API boolean: only renders compliant state if isCompliant is true.
 */
export default function ShariahBadge({
  isCompliant,
  size = 'sm',
  fullLabel = false,
  showLabel = true,
  showNonCompliant = false,
  className = '',
  tooltip = '',
}) {
  // Never assume compliance: only true means compliant
  const compliant = isCompliant === true

  if (!compliant && !showNonCompliant) {
    return null
  }

  const sizes = {
    xs: {
      badge: 'px-1.5 py-0.5 text-[10px] gap-1',
      icon: 'w-3 h-3',
    },
    sm: {
      badge: 'px-2 py-0.5 text-xs gap-1.5',
      icon: 'w-3.5 h-3.5',
    },
    md: {
      badge: 'px-2.5 py-1 text-xs gap-1.5 font-medium',
      icon: 'w-4 h-4',
    },
    lg: {
      badge: 'px-3 py-1.5 text-sm gap-2 font-semibold',
      icon: 'w-4.5 h-4.5',
    },
  }

  const s = sizes[size] || sizes.sm
  const labelText = fullLabel ? 'Shariah Compliant' : 'Shariah'
  const titleText = tooltip || (compliant
    ? 'Shariah Compliant · Meets KMI-30 / Meezan AAOIFI ethical screening criteria'
    : 'Not compliant with Shariah criteria')

  if (!compliant && showNonCompliant) {
    return (
      <span
        className={`shariah-badge inline-flex items-center rounded-md font-medium text-slate-500 dark:text-slate-400 bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 select-none ${s.badge} ${className}`}
        title={titleText}
        role="status"
        aria-label="Not Shariah Compliant"
      >
        <span>Non-Compliant</span>
      </span>
    )
  }

  return (
    <span
      className={`shariah-badge inline-flex items-center rounded-md font-medium transition-colors select-none text-emerald-800 dark:text-emerald-300 bg-emerald-50 dark:bg-emerald-950/60 border border-emerald-200 dark:border-emerald-800/80 shadow-2xs ${s.badge} ${className}`}
      title={titleText}
      role="status"
      aria-label="Shariah Compliant"
    >
      <MosqueIcon className={`${s.icon} text-emerald-600 dark:text-emerald-400`} />
      {showLabel && (
        <span className="font-semibold tracking-tight">{labelText}</span>
      )}
    </span>
  )
}
