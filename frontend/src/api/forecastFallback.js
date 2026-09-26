/**
 * Schema-compliant fallback datasets for PSX stock forecasts.
 * Conforms 100% to backend FastAPI schemas:
 * - ForecastResponse (app.ml.serving.schemas)
 * - ForecastHistoryResponse (app.ml.serving.schemas)
 */

export const FALLBACK_STOCK_FORECASTS = {
  MEBL: {
    '1D': {
      symbol: 'MEBL',
      horizon: '1D',
      direction: 'bullish',
      confidence: 0.684,
      probabilities: { bullish: 68.4, bearish: 18.2, sideways: 13.4 },
      as_of_date: '2026-09-25',
      target_date: '2026-09-28',
      current_price: 345.50,
      target_price: 358.00,
      expected_range: null,
      stop_loss: 337.00,
      signal_rating: 'Strong Buy',
      upside_pct: 3.62,
      downside_pct: -2.46,
      risk_reward_ratio: 1.47,
      price_target_rationale: 'ATR target positioned at 1.5x 14-day volatility with stop-loss anchored below 20-day exponential moving average.',
      model_version: 'ensemble',
      gate_reason: 'agree(bullish)',
      models: {
        gru: { direction: 'bullish', bullish_pct: 71.2, bearish_pct: 16.5, sideways_pct: 12.3, gap_pp: 54.7 },
        xgb: { direction: 'bullish', bullish_pct: 65.6, bearish_pct: 19.9, sideways_pct: 14.5, gap_pp: 45.7 },
      },
      market_context: {
        market_return_5d: 0.0145,
        market_return_20d: 0.0482,
        stock_return_20d: 0.0720,
        stock_relative_return_20d: 0.0238,
      },
    },
    '1W': {
      symbol: 'MEBL',
      horizon: '1W',
      direction: 'bullish',
      confidence: 0.642,
      probabilities: { bullish: 64.2, bearish: 21.0, sideways: 14.8 },
      as_of_date: '2026-09-25',
      target_date: '2026-10-02',
      current_price: 345.50,
      target_price: 372.00,
      expected_range: null,
      stop_loss: 331.00,
      signal_rating: 'Buy',
      upside_pct: 7.67,
      downside_pct: -4.20,
      risk_reward_ratio: 1.83,
      price_target_rationale: 'Multi-day momentum continuation confirmed across banking sector index.',
      model_version: 'ensemble',
      gate_reason: 'agree(bullish)',
      models: {
        gru: { direction: 'bullish', bullish_pct: 66.0, bearish_pct: 19.5, sideways_pct: 14.5, gap_pp: 46.5 },
        xgb: { direction: 'bullish', bullish_pct: 62.4, bearish_pct: 22.5, sideways_pct: 15.1, gap_pp: 39.9 },
      },
      market_context: {
        market_return_5d: 0.0145,
        market_return_20d: 0.0482,
        stock_return_20d: 0.0720,
        stock_relative_return_20d: 0.0238,
      },
    },
    '1M': {
      symbol: 'MEBL',
      horizon: '1M',
      direction: 'bullish',
      confidence: 0.598,
      probabilities: { bullish: 59.8, bearish: 24.5, sideways: 15.7 },
      as_of_date: '2026-09-25',
      target_date: '2026-10-26',
      current_price: 345.50,
      target_price: 395.00,
      expected_range: null,
      stop_loss: 322.00,
      signal_rating: 'Buy',
      upside_pct: 14.33,
      downside_pct: -6.80,
      risk_reward_ratio: 2.11,
      price_target_rationale: 'Long-term dividend accretion and Shariah banking sector expansion.',
      model_version: 'ensemble',
      gate_reason: 'agree(bullish)',
      models: {
        gru: { direction: 'bullish', bullish_pct: 61.5, bearish_pct: 23.0, sideways_pct: 15.5, gap_pp: 38.5 },
        xgb: { direction: 'bullish', bullish_pct: 58.1, bearish_pct: 26.0, sideways_pct: 15.9, gap_pp: 32.1 },
      },
      market_context: {
        market_return_5d: 0.0145,
        market_return_20d: 0.0482,
        stock_return_20d: 0.0720,
        stock_relative_return_20d: 0.0238,
      },
    },
  },
  OGDC: {
    '1D': {
      symbol: 'OGDC',
      horizon: '1D',
      direction: 'uncertain',
      confidence: 0.608,
      probabilities: { bullish: 60.8, bearish: 39.2, sideways: 0.0 },
      as_of_date: '2026-09-25',
      target_date: '2026-09-28',
      current_price: 316.20,
      target_price: null,
      expected_range: { low: 304.52, high: 327.88, method: 'atr_range' },
      stop_loss: null,
      signal_rating: 'Hold / Neutral',
      upside_pct: null,
      downside_pct: null,
      risk_reward_ratio: null,
      price_target_rationale: "Price target and stop-loss levels are omitted in 'uncertain' regime to avoid misleading projections.",
      model_version: 'ensemble',
      gate_reason: 'near_tie(xgb_gap=1.9pp)',
      models: {
        gru: { direction: 'bullish', bullish_pct: 60.8, bearish_pct: 39.2, sideways_pct: 0.0, gap_pp: 21.6 },
        xgb: { direction: 'bullish', bullish_pct: 50.9, bearish_pct: 49.1, sideways_pct: 0.0, gap_pp: 1.8 },
      },
      market_context: {
        market_return_5d: -0.0020,
        market_return_20d: -0.0641,
        stock_return_20d: -0.0102,
        stock_relative_return_20d: 0.0700,
      },
    },
    '1W': {
      symbol: 'OGDC',
      horizon: '1W',
      direction: 'bullish',
      confidence: 0.575,
      probabilities: { bullish: 57.5, bearish: 28.5, sideways: 14.0 },
      as_of_date: '2026-09-25',
      target_date: '2026-10-02',
      current_price: 316.20,
      target_price: 334.00,
      expected_range: null,
      stop_loss: 305.00,
      signal_rating: 'Buy',
      upside_pct: 5.63,
      downside_pct: -3.54,
      risk_reward_ratio: 1.59,
      price_target_rationale: 'Brent crude recovery trend and circular debt resolution progress.',
      model_version: 'ensemble',
      gate_reason: 'agree(bullish)',
      models: {
        gru: { direction: 'bullish', bullish_pct: 59.0, bearish_pct: 27.0, sideways_pct: 14.0, gap_pp: 32.0 },
        xgb: { direction: 'bullish', bullish_pct: 56.0, bearish_pct: 30.0, sideways_pct: 14.0, gap_pp: 26.0 },
      },
      market_context: {
        market_return_5d: -0.0020,
        market_return_20d: -0.0641,
        stock_return_20d: -0.0102,
        stock_relative_return_20d: 0.0700,
      },
    },
    '1M': {
      symbol: 'OGDC',
      horizon: '1M',
      direction: 'bullish',
      confidence: 0.550,
      probabilities: { bullish: 55.0, bearish: 31.0, sideways: 14.0 },
      as_of_date: '2026-09-25',
      target_date: '2026-10-26',
      current_price: 316.20,
      target_price: 352.00,
      expected_range: null,
      stop_loss: 295.00,
      signal_rating: 'Buy',
      upside_pct: 11.32,
      downside_pct: -6.70,
      risk_reward_ratio: 1.69,
      price_target_rationale: 'Long-term hydrocarbon production stability and institutional dividend yield.',
      model_version: 'ensemble',
      gate_reason: 'agree(bullish)',
      models: {
        gru: { direction: 'bullish', bullish_pct: 56.5, bearish_pct: 29.5, sideways_pct: 14.0, gap_pp: 27.0 },
        xgb: { direction: 'bullish', bullish_pct: 53.5, bearish_pct: 32.5, sideways_pct: 14.0, gap_pp: 21.0 },
      },
      market_context: {
        market_return_5d: -0.0020,
        market_return_20d: -0.0641,
        stock_return_20d: -0.0102,
        stock_relative_return_20d: 0.0700,
      },
    },
  },
  SYS: {
    '1D': {
      symbol: 'SYS',
      horizon: '1D',
      direction: 'bullish',
      confidence: 0.655,
      probabilities: { bullish: 65.5, bearish: 20.5, sideways: 14.0 },
      as_of_date: '2026-09-25',
      target_date: '2026-09-28',
      current_price: 520.00,
      target_price: 544.00,
      expected_range: null,
      stop_loss: 504.00,
      signal_rating: 'Strong Buy',
      upside_pct: 4.62,
      downside_pct: -3.08,
      risk_reward_ratio: 1.50,
      price_target_rationale: 'Export IT revenue momentum and overseas contract expansion.',
      model_version: 'ensemble',
      gate_reason: 'agree(bullish)',
      models: {
        gru: { direction: 'bullish', bullish_pct: 68.0, bearish_pct: 18.0, sideways_pct: 14.0, gap_pp: 50.0 },
        xgb: { direction: 'bullish', bullish_pct: 63.0, bearish_pct: 23.0, sideways_pct: 14.0, gap_pp: 40.0 },
      },
      market_context: {
        market_return_5d: 0.0120,
        market_return_20d: 0.0380,
        stock_return_20d: 0.0850,
        stock_relative_return_20d: 0.0470,
      },
    },
    '1W': {
      symbol: 'SYS',
      horizon: '1W',
      direction: 'bullish',
      confidence: 0.620,
      probabilities: { bullish: 62.0, bearish: 22.0, sideways: 16.0 },
      as_of_date: '2026-09-25',
      target_date: '2026-10-02',
      current_price: 520.00,
      target_price: 565.00,
      expected_range: null,
      stop_loss: 495.00,
      signal_rating: 'Buy',
      upside_pct: 8.65,
      downside_pct: -4.81,
      risk_reward_ratio: 1.80,
      price_target_rationale: 'IT export incentives and USD realization margin buffer.',
      model_version: 'ensemble',
      gate_reason: 'agree(bullish)',
      models: {
        gru: { direction: 'bullish', bullish_pct: 64.0, bearish_pct: 20.0, sideways_pct: 16.0, gap_pp: 44.0 },
        xgb: { direction: 'bullish', bullish_pct: 60.0, bearish_pct: 24.0, sideways_pct: 16.0, gap_pp: 36.0 },
      },
      market_context: {
        market_return_5d: 0.0120,
        market_return_20d: 0.0380,
        stock_return_20d: 0.0850,
        stock_relative_return_20d: 0.0470,
      },
    },
    '1M': {
      symbol: 'SYS',
      horizon: '1M',
      direction: 'bullish',
      confidence: 0.580,
      probabilities: { bullish: 58.0, bearish: 25.0, sideways: 17.0 },
      as_of_date: '2026-09-25',
      target_date: '2026-10-26',
      current_price: 520.00,
      target_price: 610.00,
      expected_range: null,
      stop_loss: 475.00,
      signal_rating: 'Buy',
      upside_pct: 17.31,
      downside_pct: -8.65,
      risk_reward_ratio: 2.00,
      price_target_rationale: 'Generative AI service pipeline and digital transformation contracts.',
      model_version: 'ensemble',
      gate_reason: 'agree(bullish)',
      models: {
        gru: { direction: 'bullish', bullish_pct: 60.0, bearish_pct: 23.0, sideways_pct: 17.0, gap_pp: 37.0 },
        xgb: { direction: 'bullish', bullish_pct: 56.0, bearish_pct: 27.0, sideways_pct: 17.0, gap_pp: 29.0 },
      },
      market_context: {
        market_return_5d: 0.0120,
        market_return_20d: 0.0380,
        stock_return_20d: 0.0850,
        stock_relative_return_20d: 0.0470,
      },
    },
  },
}

// Generate realistic historical forecast accuracy records
export function generateFallbackHistory(symbol = 'MEBL', limit = 15) {
  const isMebl = symbol.toUpperCase() === 'MEBL'
  const isSys = symbol.toUpperCase() === 'SYS'
  const accuracy = isMebl ? 0.769 : isSys ? 0.714 : 0.667

  const items = []
  const baseDate = new Date('2026-09-25')

  for (let i = 0; i < limit; i++) {
    const pDate = new Date(baseDate)
    pDate.setDate(baseDate.getDate() - (i * 2 + 1))
    const tDate = new Date(pDate)
    tDate.setDate(pDate.getDate() + 1)

    const isPending = i < 2
    const wasCorrect = isPending ? null : (i % 4 !== 1)
    const direction = i % 5 === 0 ? 'sideways' : (i % 6 === 2 ? 'bearish' : 'bullish')
    const conf = Number((0.55 + ((i * 7) % 25) / 100).toFixed(3))

    items.push({
      predicted_at: pDate.toISOString(),
      predicted_direction: direction,
      probabilities: {
        bullish: direction === 'bullish' ? Math.round(conf * 100) : 22,
        bearish: direction === 'bearish' ? Math.round(conf * 100) : 18,
        sideways: direction === 'sideways' ? Math.round(conf * 100) : Math.max(0, 100 - (direction === 'bullish' ? Math.round(conf * 100) + 18 : Math.round(conf * 100) + 22)),
      },
      confidence: conf,
      target_date: tDate.toISOString().slice(0, 10),
      actual: isPending
        ? {
            status: 'pending_target_date',
            direction: 'pending',
            was_correct: null,
            evaluation_note: 'Prediction active. Target date trading session in progress.',
          }
        : {
            status: 'evaluated',
            direction: wasCorrect ? direction : (direction === 'bullish' ? 'bearish' : 'bullish'),
            was_correct: wasCorrect,
            evaluation_note: wasCorrect ? 'Target hit within forecast window.' : 'Opposite market move occurred.',
          },
    })
  }

  return {
    symbol: symbol.toUpperCase(),
    horizon: '1D',
    count: items.length,
    accuracy: accuracy,
    history: items,
  }
}
