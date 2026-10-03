function finiteSeries(series) {
  return (Array.isArray(series) ? series : []).filter(
    (point) => point && point.value != null && Number.isFinite(Number(point.value)),
  ).map((point) => ({ year: point.year, value: Number(point.value) }));
}

function recentChange(series, count = 3) {
  const points = finiteSeries(series).slice(-count);
  if (points.length < count) return null;
  return { first: points[0].value, last: points.at(-1).value, delta: points.at(-1).value - points[0].value };
}

function relativeChange(change) {
  if (!change || change.first <= 0) return null;
  return change.delta / Math.abs(change.first);
}

function recentOwnershipChange(series) {
  const points = finiteSeries(series);
  return recentChange(points, points.length >= 5 ? 5 : 3);
}

function addDirectionalSignal(signals, series, label, threshold = 1.5) {
  const change = recentChange(series);
  if (!change) return;
  if (change.delta >= threshold) signals.positive.push(`${label} improving`);
  else if (change.delta <= -threshold) signals.watch.push(`${label} declining`);
}

function addGrowthSignal(signals, series, label) {
  const change = recentChange(series);
  if (!change) return;
  const points = finiteSeries(series).slice(-3);
  if (change.delta <= -5 || (change.first > 0 && change.last < 0)) {
    signals.watch.push(`${label} growth deteriorating`);
  } else if (change.delta >= 5) {
    signals.positive.push(`${label} growth strengthening`);
  } else if (points.every((point) => point.value > 0)) {
    signals.positive.push(`${label} growth consistently positive`);
  }
}

function addAbsoluteTrendSignal(signals, series, positiveDecreaseLabel, watchIncreaseLabel, threshold) {
  const change = recentChange(series);
  if (!change) return;
  const scale = Math.max(Math.abs(change.first), Math.abs(change.last));
  if (!scale) return;
  const movement = change.delta / scale;
  if (movement <= -threshold) signals.positive.push(positiveDecreaseLabel);
  else if (movement >= threshold) signals.watch.push(watchIncreaseLabel);
}

function institutionalHolding(trends) {
  const fii = new Map(finiteSeries(trends.fii_holding).map((point) => [point.year, point.value]));
  return finiteSeries(trends.dii_holding)
    .filter((point) => fii.has(point.year))
    .map((point) => ({ year: point.year, value: point.value + fii.get(point.year) }));
}

export function buildFundamentalSignals(data = {}) {
  const trends = data.trends || {};
  const quality = data.earnings_quality || {};
  const dilution = data.dilution || {};
  const signals = { positive: [], watch: [] };

  addDirectionalSignal(signals, trends.roe, "ROE");
  addDirectionalSignal(signals, trends.roce, "ROCE");
  addDirectionalSignal(signals, trends.operating_margin, "Operating margin");
  addGrowthSignal(signals, trends.revenue_growth, "Revenue");
  addGrowthSignal(signals, trends.profit_growth, "Profit");
  addGrowthSignal(signals, trends.eps_growth, "EPS");

  const fcfChange = recentChange(quality.fcf);
  const fcfGrowthChange = recentChange(quality.fcf_growth);
  const fcfGrowthPoints = finiteSeries(quality.fcf_growth).slice(-3);
  const profitChange = recentChange(quality.net_profit);
  if (fcfChange && profitChange) {
    const fcfScale = Math.max(Math.abs(fcfChange.first), Math.abs(fcfChange.last));
    const profitScale = Math.max(Math.abs(profitChange.first), Math.abs(profitChange.last));
    const fcfMovement = fcfScale ? fcfChange.delta / fcfScale : 0;
    const profitMovement = profitScale ? profitChange.delta / profitScale : 0;
    if (fcfMovement <= -0.15 && profitMovement >= 0.1) {
      signals.watch.push("FCF deteriorating while profit grows");
    } else if (
      fcfMovement >= 0.15 ||
      (fcfGrowthChange && (fcfGrowthChange.delta >= 5 || fcfGrowthPoints.every((point) => point.value > 0)))
    ) {
      signals.positive.push("FCF improving");
    }
  }

  const cashConversion = finiteSeries(trends.cash_conversion).slice(-3);
  if (cashConversion.length === 3) {
    const change = cashConversion.at(-1).value - cashConversion[0].value;
    if (cashConversion.every((point) => point.value >= 100)) {
      signals.positive.push("Strong cash conversion");
    } else if (change >= 20 && cashConversion.at(-1).value >= 60) {
      signals.positive.push("Cash conversion improving");
    } else if (cashConversion.every((point) => point.value < 50)) {
      signals.watch.push("CFO / Net Profit persistently weak");
    }
  }

  const debtEquityMovement = relativeChange(recentChange(trends.debt_equity));
  if (debtEquityMovement != null) {
    if (debtEquityMovement <= -0.15) signals.positive.push("Debt/Equity declining");
    else if (debtEquityMovement >= 0.15) signals.watch.push("Debt/Equity increasing");
  }
  addAbsoluteTrendSignal(signals, trends.debt, "Debt declining", "Debt increasing materially", 0.2);

  const promoters = recentOwnershipChange(trends.promoter_holding);
  if (promoters) {
    if (promoters.delta <= -2) signals.watch.push("Promoter holding declining");
    else if (promoters.delta >= -1) signals.positive.push("Promoter holding stable/increasing");
  }

  const institutions = recentOwnershipChange(institutionalHolding(trends));
  if (institutions) {
    if (institutions.delta <= -2) signals.watch.push("FII/DII holding declining");
    else if (institutions.delta >= 2) signals.positive.push("FII/DII holding increasing");
  }

  const shareCountCagr = dilution.share_count_cagr_5y ?? dilution.share_count_cagr_3y;
  if (shareCountCagr != null && Number.isFinite(Number(shareCountCagr))) {
    if (Number(shareCountCagr) >= 0.03) signals.watch.push("Share count increasing materially");
    else if (Number(shareCountCagr) <= 0.01) signals.positive.push("Share count stable/declining");
  }

  const profitEpsGap = dilution.profit_vs_eps_cagr_gap_5y ?? dilution.profit_vs_eps_cagr_gap_3y;
  if (profitEpsGap != null && Number.isFinite(Number(profitEpsGap)) && Number(profitEpsGap) >= 0.03) {
    signals.watch.push("Profit growth materially exceeds EPS growth");
  }

  return signals;
}