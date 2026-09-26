import React from 'react'

export default function FloatingCopilotButton({ onClick }) {
  return (
    <aside
      aria-label="AI Copilot Quick Access"
      className="fixed bottom-20 md:bottom-6 right-4 md:right-6 z-40 print:hidden"
    >
      <button
        type="button"
        onClick={onClick}
        title="AI Copilot"
        aria-label="Open AI Copilot"
        className="group relative flex items-center justify-center w-12 h-12 rounded-full bg-slate-900/95 dark:bg-slate-900/95 hover:bg-slate-900 text-white backdrop-blur-md border border-slate-700/80 hover:border-emerald-500/60 shadow-lg shadow-black/30 hover:shadow-xl hover:shadow-emerald-500/20 transition-all duration-300 hover:scale-105 active:scale-95 cursor-pointer focus:outline-hidden focus:ring-2 focus:ring-emerald-500/50"
      >
        {/* Glowing Background Radial on Hover */}
        <span
          className="pointer-events-none absolute -inset-0.5 rounded-full bg-gradient-to-r from-emerald-500/30 via-teal-500/20 to-cyan-500/30 opacity-0 group-hover:opacity-100 blur-sm transition-opacity duration-300"
          aria-hidden="true"
        />

        {/* AI Logo Icon */}
        <svg
          className="w-5 h-5 text-emerald-400 group-hover:text-emerald-300 transition-colors transform group-hover:rotate-6 duration-300"
          viewBox="0 0 24 24"
          fill="currentColor"
          aria-hidden="true"
        >
          <path d="m12 2 2.4 6.6 6.6 2.4-6.6 2.4L12 20l-2.4-6.6L3 11l6.6-2.4L12 2Z" />
        </svg>

        {/* Active status pulse */}
        <span className="absolute top-1 right-1 flex h-2.5 w-2.5" aria-hidden="true">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
          <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500" />
        </span>

        {/* Hover Tooltip (appears to the left) */}
        <span
          role="tooltip"
          className="pointer-events-none absolute right-full mr-3 top-1/2 -translate-y-1/2 px-2.5 py-1 rounded-lg bg-slate-900/95 text-slate-100 text-xs font-medium tracking-wide shadow-md border border-slate-700/80 whitespace-nowrap opacity-0 -translate-x-1 group-hover:opacity-100 group-hover:translate-x-0 transition-all duration-200"
        >
          AI Copilot
        </span>
      </button>
    </aside>
  )
}
