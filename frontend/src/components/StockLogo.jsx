import React, { useState, useEffect } from 'react'

const SIZES = {
  xs: { box: 'w-5 h-5 min-w-[20px]', img: 'w-4 h-4', text: 'text-[9px]', p: 'p-0.5' },
  sm: { box: 'w-7 h-7 min-w-[28px]', img: 'w-5 h-5', text: 'text-[10px]', p: 'p-0.5' },
  md: { box: 'w-9 h-9 min-w-[36px]', img: 'w-7 h-7', text: 'text-xs', p: 'p-1' },
  lg: { box: 'w-12 h-12 min-w-[48px]', img: 'w-9 h-9', text: 'text-sm font-semibold', p: 'p-1.5' },
  xl: { box: 'w-16 h-16 min-w-[64px]', img: 'w-12 h-12', text: 'text-base font-bold', p: 'p-2' },
}

// Known official domain map for Pakistani listed companies for secondary favicon resolution
const KNOWN_DOMAINS = {
  OGDC: 'ogdcl.com',
  MARI: 'marienergies.com.pk',
  SYS: 'systemsltd.com',
  LUCK: 'lucky-cement.com',
  MEBL: 'meezanbank.com',
  MCB: 'mcb.com.pk',
  ENGRO: 'engro.com',
  HUBC: 'hubpower.com',
  FFC: 'ffc.com.pk',
  UBL: 'ubldigital.com',
  HBL: 'hbl.com',
  PSO: 'psopk.com',
  EFERT: 'engrofertilizers.com',
  BAHL: 'bankalhabib.com',
  BAFL: 'bankalfalah.com',
  POL: 'papkpetroleum.com.pk',
  PPL: 'ppl.com.pk',
  FCCL: 'fauji.org.pk',
  DGKC: 'dgcement.com',
  MLCF: 'mapleleaf.com.pk',
  CHCC: 'cherat.com',
  SEARL: 'searlecompany.com',
  AGP: 'agp.com.pk',
  ABOT: 'abbott.com.pk',
  TRG: 'trgworld.com',
  AVN: 'avanceon.com',
  OCTOPUS: 'octopusdt.com',
  KEL: 'ke.com.pk',
  KAPCO: 'kapco.com.pk',
  SNGP: 'sngpl.com.pk',
  SSGC: 'ssgc.com.pk',
}

/**
 * Reusable official stock logo component.
 * Displays official company logo with proper aspect ratio, clean background,
 * and reliable multi-source fallback (API URL -> Official Vector SVG -> Favicon -> Clean Neutral Initial).
 */
export default function StockLogo({
  ticker = '',
  symbol = '',
  companyName = '',
  name = '',
  logoUrl = '',
  size = 'md',
  className = '',
  rounded = 'rounded-xl',
}) {
  const cleanSymbol = (ticker || symbol || '').toUpperCase().trim()
  const cleanName = companyName || name || cleanSymbol
  const sizeConfig = SIZES[size] || SIZES.md

  // Stage 0: direct logoUrl if given
  // Stage 1: official SVG from primary PSX logo CDN
  // Stage 2: domain favicon from Google CDN
  // Stage 3: clean fallback initials
  const [sourceIndex, setSourceIndex] = useState(0)

  // Candidate sources
  const candidateUrls = []
  if (logoUrl) candidateUrls.push(logoUrl)
  if (cleanSymbol) {
    candidateUrls.push(`https://www.tickeranalysts.com/images/logos/${cleanSymbol}.svg`)
    const domain = KNOWN_DOMAINS[cleanSymbol]
    if (domain) {
      candidateUrls.push(`https://www.google.com/s2/favicons?domain=${domain}&sz=128`)
    }
  }

  // Reset when symbol changes
  useEffect(() => {
    setSourceIndex(0)
  }, [cleanSymbol, logoUrl])

  const currentUrl = sourceIndex < candidateUrls.length ? candidateUrls[sourceIndex] : null

  const handleImageError = () => {
    setSourceIndex((prev) => prev + 1)
  }

  const initials = cleanSymbol.slice(0, 3) || 'PSX'

  return (
    <div
      className={`official-stock-logo inline-flex items-center justify-center shrink-0 bg-white dark:bg-slate-800 border border-slate-200/90 dark:border-slate-700/90 shadow-2xs select-none transition-all ${sizeConfig.box} ${rounded} ${className}`}
      title={cleanName ? `${cleanName} (${cleanSymbol})` : cleanSymbol}
      aria-label={`${cleanSymbol} logo`}
    >
      {currentUrl ? (
        <img
          key={currentUrl}
          src={currentUrl}
          alt={`${cleanSymbol} logo`}
          className={`w-full h-full object-contain ${sizeConfig.p} ${rounded}`}
          onError={handleImageError}
          loading="lazy"
          decoding="async"
        />
      ) : (
        <span
          className={`font-mono font-bold tracking-tight text-slate-600 dark:text-slate-300 leading-none select-none ${sizeConfig.text}`}
        >
          {initials}
        </span>
      )}
    </div>
  )
}
