/**
 * PSX Risk Analytics fallback & benchmark demo datasets.
 * Conforms 100% to backend FastAPI schemas:
 * - RiskVaRResponse (app.ml.serving.schemas)
 * - StressTestResponse (app.ml.serving.schemas)
 * - MonteCarloResultResponse (app.ml.serving.schemas)
 */

export const DEMO_PORTFOLIO_HOLDINGS = [
  { symbol: 'MEBL', name: 'Meezan Bank Ltd', sector: 'Commercial Banks', weight_pct: 30, current_value: 750000 },
  { symbol: 'OGDC', name: 'Oil & Gas Development Co', sector: 'Oil & Gas', weight_pct: 25, current_value: 625000 },
  { symbol: 'SYS', name: 'Systems Limited', sector: 'Technology', weight_pct: 20, current_value: 500000 },
  { symbol: 'HUBC', name: 'Hub Power Company', sector: 'Power Generation', weight_pct: 15, current_value: 375000 },
  { symbol: 'ENGRO', name: 'Engro Corporation', sector: 'Fertilizer / Conglomerate', weight_pct: 10, current_value: 250000 },
]

export const FALLBACK_VAR_MATRIX = {
  '90': {
    '1D': { confidence: 90, horizon: '1D', var_value: -0.0135, cvar_value: -0.0210, method: 'historical_simulation', num_observations: 252, annualized_volatility: 0.1945 },
    '1W': { confidence: 90, horizon: '1W', var_value: -0.0302, cvar_value: -0.0469, method: 'historical_simulation', num_observations: 252, annualized_volatility: 0.1945 },
    '1M': { confidence: 90, horizon: '1M', var_value: -0.0618, cvar_value: -0.0962, method: 'historical_simulation', num_observations: 252, annualized_volatility: 0.1945 },
  },
  '95': {
    '1D': { confidence: 95, horizon: '1D', var_value: -0.0182, cvar_value: -0.0275, method: 'historical_simulation', num_observations: 252, annualized_volatility: 0.1945 },
    '1W': { confidence: 95, horizon: '1W', var_value: -0.0407, cvar_value: -0.0615, method: 'historical_simulation', num_observations: 252, annualized_volatility: 0.1945 },
    '1M': { confidence: 95, horizon: '1M', var_value: -0.0834, cvar_value: -0.1260, method: 'historical_simulation', num_observations: 252, annualized_volatility: 0.1945 },
  },
  '99': {
    '1D': { confidence: 99, horizon: '1D', var_value: -0.0295, cvar_value: -0.0385, method: 'historical_simulation', num_observations: 252, annualized_volatility: 0.1945 },
    '1W': { confidence: 99, horizon: '1W', var_value: -0.0659, cvar_value: -0.0861, method: 'historical_simulation', num_observations: 252, annualized_volatility: 0.1945 },
    '1M': { confidence: 99, horizon: '1M', var_value: -0.1352, cvar_value: -0.1765, method: 'historical_simulation', num_observations: 252, annualized_volatility: 0.1945 },
  },
}

export const FALLBACK_STRESS_SCENARIOS = {
  '2008_crash': {
    scenario: '2008_crash',
    name: '2008 Global Financial Crisis',
    description: 'Simulates the 2008 GFC: KSE-100 fell ~45% peak-to-trough over 6 months with acute liquidity freeze.',
    portfolio_impact: -0.4215,
    portfolio_impact_value: -1053750,
    worst_case_loss: -0.60,
    volatility_multiplier: 2.5,
    recovery_days: 540,
    current_value: 2500000,
    stressed_value: 1446250,
    holding_impacts: [
      { symbol: 'MEBL', sector: 'Commercial Banks', current_value: 750000, weight_pct: 30.0, shock_pct: -55.0, impact_value: -412500, worst_case_value: 206250 },
      { symbol: 'OGDC', sector: 'Oil & Gas', current_value: 625000, weight_pct: 25.0, shock_pct: -40.0, impact_value: -250000, worst_case_value: 291667 },
      { symbol: 'SYS', sector: 'Technology', current_value: 500000, weight_pct: 20.0, shock_pct: -60.0, impact_value: -300000, worst_case_value: 133333 },
      { symbol: 'HUBC', sector: 'Power Generation', current_value: 375000, weight_pct: 15.0, shock_pct: -25.0, impact_value: -93750, worst_case_value: 281250 },
      { symbol: 'ENGRO', sector: 'Fertilizer / Conglomerate', current_value: 250000, weight_pct: 10.0, shock_pct: -35.0, impact_value: -87500, worst_case_value: 145833 },
    ],
  },
  'pkr_devaluation': {
    scenario: 'pkr_devaluation',
    name: 'Sharp PKR Devaluation',
    description: 'Simulates a sudden 20% currency devaluation: tech/dollar earners gain resilience while import-heavy industries compress.',
    portfolio_impact: -0.1420,
    portfolio_impact_value: -355000,
    worst_case_loss: -0.25,
    volatility_multiplier: 1.8,
    recovery_days: 180,
    current_value: 2500000,
    stressed_value: 2145000,
    holding_impacts: [
      { symbol: 'MEBL', sector: 'Commercial Banks', current_value: 750000, weight_pct: 30.0, shock_pct: -15.0, impact_value: -112500, worst_case_value: 562500 },
      { symbol: 'OGDC', sector: 'Oil & Gas', current_value: 625000, weight_pct: 25.0, shock_pct: -5.0, impact_value: -31250, worst_case_value: 531250 },
      { symbol: 'SYS', sector: 'Technology', current_value: 500000, weight_pct: 20.0, shock_pct: 10.0, impact_value: 50000, worst_case_value: 520000 },
      { symbol: 'HUBC', sector: 'Power Generation', current_value: 375000, weight_pct: 15.0, shock_pct: -20.0, impact_value: -75000, worst_case_value: 281250 },
      { symbol: 'ENGRO', sector: 'Fertilizer / Conglomerate', current_value: 250000, weight_pct: 10.0, shock_pct: -18.0, impact_value: -45000, worst_case_value: 187500 },
    ],
  },
  'covid_crash': {
    scenario: 'covid_crash',
    name: 'COVID-19 Market Halt',
    description: 'Simulates the March 2020 rapid sell-off: acute demand shock, circuit breakers tripped, high short-term correlation spike.',
    portfolio_impact: -0.3150,
    portfolio_impact_value: -787500,
    worst_case_loss: -0.40,
    volatility_multiplier: 3.0,
    recovery_days: 240,
    current_value: 2500000,
    stressed_value: 1712500,
    holding_impacts: [
      { symbol: 'MEBL', sector: 'Commercial Banks', current_value: 750000, weight_pct: 30.0, shock_pct: -32.0, impact_value: -240000, worst_case_value: 460000 },
      { symbol: 'OGDC', sector: 'Oil & Gas', current_value: 625000, weight_pct: 25.0, shock_pct: -38.0, impact_value: -237500, worst_case_value: 350000 },
      { symbol: 'SYS', sector: 'Technology', current_value: 500000, weight_pct: 20.0, shock_pct: -15.0, impact_value: -75000, worst_case_value: 400000 },
      { symbol: 'HUBC', sector: 'Power Generation', current_value: 375000, weight_pct: 15.0, shock_pct: -28.0, impact_value: -105000, worst_case_value: 255000 },
      { symbol: 'ENGRO', sector: 'Fertilizer / Conglomerate', current_value: 250000, weight_pct: 10.0, shock_pct: -26.0, impact_value: -65000, worst_case_value: 175000 },
    ],
  },
  'interest_rate_hike': {
    scenario: 'interest_rate_hike',
    name: 'SBP Monetary Tightening (+300bps)',
    description: 'Simulates an aggressive policy rate increase: higher cost of borrowing hurts leveraged sectors, banks benefit from margin expansion.',
    portfolio_impact: -0.0780,
    portfolio_impact_value: -195000,
    worst_case_loss: -0.15,
    volatility_multiplier: 1.4,
    recovery_days: 120,
    current_value: 2500000,
    stressed_value: 2305000,
    holding_impacts: [
      { symbol: 'MEBL', sector: 'Commercial Banks', current_value: 750000, weight_pct: 30.0, shock_pct: 8.0, impact_value: 60000, worst_case_value: 780000 },
      { symbol: 'OGDC', sector: 'Oil & Gas', current_value: 625000, weight_pct: 25.0, shock_pct: -4.0, impact_value: -25000, worst_case_value: 580000 },
      { symbol: 'SYS', sector: 'Technology', current_value: 500000, weight_pct: 20.0, shock_pct: -12.0, impact_value: -60000, worst_case_value: 410000 },
      { symbol: 'HUBC', sector: 'Power Generation', current_value: 375000, weight_pct: 15.0, shock_pct: -18.0, impact_value: -67500, worst_case_value: 290000 },
      { symbol: 'ENGRO', sector: 'Fertilizer / Conglomerate', current_value: 250000, weight_pct: 10.0, shock_pct: -14.0, impact_value: -35000, worst_case_value: 205000 },
    ],
  },
}

// Generate 40 deterministic stochastic sample paths for visualization
function generateSamplePaths(days = 30, count = 40) {
  const paths = []
  const seeds = [
    0.02, -0.015, 0.01, -0.008, 0.025, -0.03, 0.018, -0.012, 0.035, -0.045,
    0.005, -0.022, 0.012, -0.018, 0.028, -0.035, 0.015, -0.005, 0.008, -0.014,
    0.022, -0.025, 0.031, -0.019, 0.017, -0.028, 0.009, -0.011, 0.024, -0.032,
    0.014, -0.016, 0.019, -0.021, 0.027, -0.038, 0.011, -0.007, 0.006, -0.013,
  ]

  for (let i = 0; i < count; i++) {
    const drift = 0.00035 + (seeds[i % seeds.length] * 0.001)
    const vol = 0.0125 + (Math.abs(seeds[(i + 5) % seeds.length]) * 0.005)
    const path = [1.0]
    let current = 1.0

    for (let d = 1; d <= days; d++) {
      // Deterministic pseudo-random shock based on sine wave harmonics
      const phase = (d * 1.618 + i * 2.718)
      const shock = Math.sin(phase) * Math.cos(phase * 0.7)
      const dailyReturn = drift + vol * shock
      current = current * (1 + dailyReturn)
      path.push(Number(current.toFixed(5)))
    }
    paths.push(path)
  }
  return paths
}

export const FALLBACK_MONTE_CARLO = {
  job_id: 'demo_mc_psx_portfolio',
  status: 'completed',
  num_simulations: 1000,
  horizon_days: 30,
  params: {
    daily_drift: 0.00035,
    daily_volatility: 0.0125,
    annualized_drift: 0.0882,
    annualized_volatility: 0.1984,
  },
  percentiles: {
    p1: -0.1842,
    p5: -0.1315,
    p10: -0.0982,
    p25: -0.0451,
    p50: 0.0241,
    p75: 0.0894,
    p90: 0.1528,
    p95: 0.1985,
    p99: 0.2852,
  },
  stats: {
    mean_return: 0.0284,
    std_return: 0.0952,
    prob_loss: 0.3850,
    prob_loss_10pct: 0.0982,
    prob_gain_10pct: 0.2215,
    max_drawdown: -0.2150,
    best_case: 0.3125,
  },
  paths_sample: generateSamplePaths(30, 40),
  completed_at: new Date().toISOString(),
}

