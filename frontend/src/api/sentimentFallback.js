/**
 * Fallback dataset for PSX Market & Stock Sentiment Analysis.
 * Strictly adheres to backend schemas:
 * - MarketSentimentResponse
 * - SentimentResponse
 * - SentimentHistoryResponse
 * - SentimentNewsResponse
 */

export const FALLBACK_MARKET_SENTIMENT = {
  market_mood: 'bullish',
  overall_score: 0.38,
  article_count: 282,
  community_post_count: 45,
  advancing: 42,
  declining: 18,
  unchanged: 12,
  advance_decline_ratio: 2.33,
  news_sentiment_avg: 0.36,
  community_sentiment_avg: 0.42,
  score_distribution: {
    positive: 156,
    neutral: 84,
    negative: 42,
  },
};

export const FALLBACK_STOCK_SENTIMENTS = {
  MEBL: {
    symbol: 'MEBL',
    score: 0.52,
    label: 'positive',
    article_count: 18,
    trend: 'improving',
    source_breakdown: { news: 14, community: 4 },
    daily_scores: [
      { date: '2026-09-20', score: 0.45, count: 2 },
      { date: '2026-09-21', score: 0.48, count: 3 },
      { date: '2026-09-22', score: 0.50, count: 2 },
      { date: '2026-09-23', score: 0.55, count: 4 },
      { date: '2026-09-24', score: 0.51, count: 3 },
      { date: '2026-09-25', score: 0.52, count: 4 },
    ],
  },
  OGDC: {
    symbol: 'OGDC',
    score: 0.64,
    label: 'positive',
    article_count: 24,
    trend: 'improving',
    source_breakdown: { news: 19, community: 5 },
  },
  SYS: {
    symbol: 'SYS',
    score: 0.58,
    label: 'positive',
    article_count: 16,
    trend: 'improving',
    source_breakdown: { news: 12, community: 4 },
  },
  HUBC: {
    symbol: 'HUBC',
    score: 0.12,
    label: 'neutral',
    article_count: 14,
    trend: 'stable',
    source_breakdown: { news: 10, community: 4 },
  },
  ENGRO: {
    symbol: 'ENGRO',
    score: 0.41,
    label: 'positive',
    article_count: 15,
    trend: 'improving',
    source_breakdown: { news: 11, community: 4 },
  },
  UBL: {
    symbol: 'UBL',
    score: 0.35,
    label: 'positive',
    article_count: 12,
    trend: 'improving',
    source_breakdown: { news: 10, community: 2 },
  },
};

export function generateFallbackHistory(symbol = 'MEBL', period = '1M') {
  const days = period === '1W' ? 7 : period === '3M' ? 90 : period === '6M' ? 180 : period === '1Y' ? 365 : 30;
  const data = [];
  const baseScore = symbol === 'OGDC' ? 0.6 : symbol === 'HUBC' ? 0.1 : 0.45;
  const now = Date.now();

  for (let i = days - 1; i >= 0; i--) {
    const d = new Date(now - i * 86400000);
    // Sine wave + small deterministic fluctuation
    const noise = Math.sin(i * 0.4) * 0.18 + Math.cos(i * 0.7) * 0.08;
    const score = Math.max(-0.9, Math.min(0.9, Number((baseScore + noise).toFixed(2))));
    const label = score > 0.15 ? 'positive' : score < -0.15 ? 'negative' : 'neutral';
    data.push({
      date: d.toISOString().split('T')[0],
      score,
      label,
      article_count: Math.floor(Math.abs(noise) * 5) + 1,
      positive_ratio: score > 0 ? 0.7 : 0.2,
      neutral_ratio: 0.2,
      negative_ratio: score < 0 ? 0.6 : 0.1,
      trend: noise >= 0 ? 'improving' : 'declining',
    });
  }

  return {
    symbol: symbol.toUpperCase(),
    period,
    data,
  };
}

export function generateFallbackNews(symbol = 'MEBL') {
  const sym = symbol.toUpperCase();
  return {
    symbol: sym,
    total: 4,
    page: 1,
    limit: 20,
    items: [
      {
        id: `news_${sym}_1`,
        title: `${sym} Reports Strong Operational Growth & Market Leadership in Quarterly Disclosure`,
        source: 'PSX Official Announcements',
        published_at: new Date(Date.now() - 3 * 3600000).toISOString(),
        url: 'https://dps.psx.com.pk/announcements',
        sentiment: 'POSITIVE',
        sentiment_score: 0.88,
        sentiment_model: 'finbert',
      },
      {
        id: `news_${sym}_2`,
        title: `Board of Directors Approves Strategic Expansion and Dividend Recommendation for ${sym}`,
        source: 'Business Recorder',
        published_at: new Date(Date.now() - 14 * 3600000).toISOString(),
        url: 'https://www.brecorder.com',
        sentiment: 'POSITIVE',
        sentiment_score: 0.76,
        sentiment_model: 'finbert',
      },
      {
        id: `news_${sym}_3`,
        title: `Sector Analytical Review: ${sym} Demonstrates Resilience Amid Macro Headwinds`,
        source: 'Dawn Business',
        published_at: new Date(Date.now() - 28 * 3600000).toISOString(),
        url: 'https://www.dawn.com/business',
        sentiment: 'NEUTRAL',
        sentiment_score: 0.52,
        sentiment_model: 'finbert',
      },
      {
        id: `news_${sym}_4`,
        title: `${sym} Formalizes Modernized Digital Infrastructure & Technology Upgrade Agreement`,
        source: 'Mettis Global',
        published_at: new Date(Date.now() - 52 * 3600000).toISOString(),
        url: 'https://mettisglobal.news',
        sentiment: 'POSITIVE',
        sentiment_score: 0.82,
        sentiment_model: 'finbert',
      },
    ],
  };
}

