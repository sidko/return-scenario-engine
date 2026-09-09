import {
  METHODOLOGY_HASH,
  ARTIFACT_SCHEMA_VERSION,
  METHODOLOGY_VERSION,
} from './methodology.js';
import type {
  AmountParseResult,
  AssetScenarioMetrics,
  BasisPointMetricValue,
  AssetSeriesArtifact,
  ComparisonWinner,
  DrawdownResult,
  HundredthsMetricValue,
  MetricReason,
  ScenarioInput,
  ScenarioResult,
} from './types.js';

export { ARTIFACT_SCHEMA_VERSION, METHODOLOGY_HASH, METHODOLOGY_VERSION } from './methodology.js';

export const SUPPORTED_SCHEMA_VERSION = ARTIFACT_SCHEMA_VERSION;
export const SUPPORTED_METHODOLOGY_VERSION = METHODOLOGY_VERSION;
export const SUPPORTED_SERIES_BASES = ['close_index', 'adjusted_close_index'] as const;
export const DEFAULT_FIXTURE_SERIES_BASIS = 'close_index';
export const MIN_AMOUNT_CENTS = 100;
export const MAX_AMOUNT_CENTS = 1_000_000_000;
export const CAGR_DAY_COUNT = 365.25;
export const CALMAR_MIN_ABS_DRAWDOWN = 0.0001;
export const ZERO_VARIANCE_SUMSQ_EPSILON = 1e-24;
export const CORRELATION_CLAMP_TOLERANCE = 1e-12;

const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;
const DAY_MS = 24 * 60 * 60 * 1000;

function normalizeZero(value: number): number {
  return value === 0 ? 0 : value;
}

function basisPointMetricUnavailable(reason: MetricReason): BasisPointMetricValue {
  return { available: false, reason };
}

function hundredthsMetricUnavailable(reason: MetricReason): HundredthsMetricValue {
  return { available: false, reason };
}

function basisPointMetricAvailable(value: number): BasisPointMetricValue {
  if (!Number.isFinite(value)) return basisPointMetricUnavailable('nonfinite_result');
  return { available: true, value: normalizeZero(value), displayBasisPoints: displayBasisPoints(value) };
}

function hundredthsMetricAvailable(value: number): HundredthsMetricValue {
  if (!Number.isFinite(value)) return hundredthsMetricUnavailable('nonfinite_result');
  return { available: true, value: normalizeZero(value), displayHundredths: displayHundredths(value) };
}

function decimalString(value: number): string {
  const raw = Math.abs(value).toString();
  if (!raw.includes('e')) return raw;
  const [coefficient, exponentText] = raw.split('e');
  const exponent = Number(exponentText);
  const [integerPart, fractionPart = ''] = coefficient.split('.');
  const digits = `${integerPart}${fractionPart}`;
  const decimalIndex = integerPart.length + exponent;
  if (decimalIndex <= 0) return `0.${'0'.repeat(Math.abs(decimalIndex))}${digits}`;
  if (decimalIndex >= digits.length) return `${digits}${'0'.repeat(decimalIndex - digits.length)}`;
  return `${digits.slice(0, decimalIndex)}.${digits.slice(decimalIndex)}`;
}

export function roundHalfAwayFromZero(value: number, scale = 1): number {
  if (!Number.isFinite(value)) throw new Error('cannot round nonfinite value');
  if (!Number.isSafeInteger(scale) || scale <= 0) throw new Error('scale must be a positive safe integer');
  const sign = value < 0 ? -1 : 1;
  const [integerPart, fractionPart = ''] = decimalString(value).split('.');
  const numerator = BigInt(`${integerPart}${fractionPart}`.replace(/^0+(?=\d)/, '') || '0') * BigInt(scale);
  const denominator = 10n ** BigInt(fractionPart.length);
  let scaled = numerator / denominator;
  if ((numerator % denominator) * 2n >= denominator) scaled += 1n;
  if (scaled > BigInt(Number.MAX_SAFE_INTEGER)) throw new Error('rounded result exceeds safe integer range');
  const rounded = Number(scaled);
  return rounded === 0 ? 0 : sign * rounded;
}

export function displayCents(usdValue: number): number {
  return roundHalfAwayFromZero(usdValue, 100);
}

export function displayBasisPoints(decimalValue: number): number {
  return roundHalfAwayFromZero(decimalValue, 10_000);
}

export function displayHundredths(ratioValue: number): number {
  return roundHalfAwayFromZero(ratioValue, 100);
}

export function isValidCivilDate(value: unknown): value is string {
  if (typeof value !== 'string' || !DATE_RE.test(value)) return false;
  const [year, month, day] = value.split('-').map(Number);
  const parsed = new Date(Date.UTC(year, month - 1, day));
  return (
    parsed.getUTCFullYear() === year &&
    parsed.getUTCMonth() === month - 1 &&
    parsed.getUTCDate() === day
  );
}

export function civilDay(value: string): number {
  if (!isValidCivilDate(value)) throw new Error(`invalid civil date: ${value}`);
  const [year, month, day] = value.split('-').map(Number);
  return Math.floor(Date.UTC(year, month - 1, day) / DAY_MS);
}

export function firstAnniversary(value: string): string {
  if (!isValidCivilDate(value)) throw new Error(`invalid civil date: ${value}`);
  const [year, month, day] = value.split('-').map(Number);
  const shifted = new Date(Date.UTC(year + 1, month - 1, day));
  if (shifted.getUTCMonth() !== month - 1) {
    shifted.setUTCDate(0);
  }
  return shifted.toISOString().slice(0, 10);
}

export function shiftYearsBack(value: string, years: number): string {
  if (!isValidCivilDate(value)) return value;
  const [year, month, day] = value.split('-').map(Number);
  const shifted = new Date(Date.UTC(year - years, month - 1, day));
  if (shifted.getUTCMonth() !== month - 1) {
    shifted.setUTCDate(0);
  }
  return shifted.toISOString().slice(0, 10);
}

export function parseUsdAmountToCents(value: unknown): AmountParseResult {
  if (typeof value !== 'string') return { ok: false, reason: 'invalid_amount' };
  const raw = value.trim().replace(/^\$\s*/, '');
  const plainAmount = /^(0|[1-9][0-9]*)(\.[0-9]{1,2})?$/;
  const groupedAmount = /^(0|[1-9][0-9]{0,2}(,[0-9]{3})+)(\.[0-9]{1,2})?$/;
  if (!plainAmount.test(raw) && !groupedAmount.test(raw)) {
    return { ok: false, reason: 'invalid_amount' };
  }
  const [dollars, cents = ''] = raw.replaceAll(',', '').split('.');
  const parsed = Number(dollars) * 100 + Number(cents.padEnd(2, '0') || '0');
  if (!Number.isSafeInteger(parsed) || parsed < MIN_AMOUNT_CENTS || parsed > MAX_AMOUNT_CENTS) {
    return { ok: false, reason: 'invalid_amount' };
  }
  return { ok: true, cents: parsed };
}

export const parseAmountToCents = parseUsdAmountToCents;

function orderedMean(values: number[]): number {
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function sampleVariance(values: number[]): number | null {
  if (values.length < 2) return null;
  const mean = orderedMean(values);
  return values.reduce((sum, value) => sum + (value - mean) ** 2, 0) / (values.length - 1);
}

function sampleStddev(values: number[]): number | null {
  const variance = sampleVariance(values);
  return variance === null ? null : Math.sqrt(variance);
}

function simpleReturns(values: number[]): number[] {
  const returns: number[] = [];
  for (let index = 1; index < values.length; index += 1) {
    const previous = values[index - 1];
    const current = values[index];
    if (previous <= 0 || current <= 0) throw new Error('normalized indexes must be positive');
    returns.push(current / previous - 1);
  }
  return returns;
}

export function pearsonCorrelation(valuesA: number[], valuesB: number[]): HundredthsMetricValue {
  if (valuesA.length !== valuesB.length || valuesA.length < 2) {
    return hundredthsMetricUnavailable('insufficient_data');
  }
  const meanA = orderedMean(valuesA);
  const meanB = orderedMean(valuesB);
  let covariance = 0;
  let sumSqA = 0;
  let sumSqB = 0;
  for (let index = 0; index < valuesA.length; index += 1) {
    const deltaA = valuesA[index] - meanA;
    const deltaB = valuesB[index] - meanB;
    covariance += deltaA * deltaB;
    sumSqA += deltaA * deltaA;
    sumSqB += deltaB * deltaB;
  }
  if (sumSqA <= ZERO_VARIANCE_SUMSQ_EPSILON || sumSqB <= ZERO_VARIANCE_SUMSQ_EPSILON) {
    return hundredthsMetricUnavailable('zero_variance');
  }
  let correlation = covariance / Math.sqrt(sumSqA * sumSqB);
  if (Math.abs(Math.abs(correlation) - 1) <= CORRELATION_CLAMP_TOLERANCE) {
    correlation = correlation > 0 ? 1 : -1;
  } else if (correlation < -1 || correlation > 1) {
    return hundredthsMetricUnavailable('nonfinite_result');
  }
  return hundredthsMetricAvailable(correlation);
}

function drawdownStats(values: number[], dates: string[]): DrawdownResult {
  if (values.length < 2) {
    return {
      maxDrawdown: basisPointMetricUnavailable('insufficient_data'),
      peakDate: null,
      troughDate: null,
      recoveryDate: null,
      recoveryDays: null,
      recoveryStatus: 'not_applicable',
    };
  }

  let runningPeak = values[0];
  let runningPeakAtTrough = values[0];
  let troughIndex = 0;
  let maxDrawdown = 0;

  for (let index = 0; index < values.length; index += 1) {
    const value = values[index];
    if (value >= runningPeak) runningPeak = value;
    const drawdown = value / runningPeak - 1;
    if (drawdown < maxDrawdown) {
      maxDrawdown = drawdown;
      troughIndex = index;
      runningPeakAtTrough = runningPeak;
    }
  }

  if (maxDrawdown === 0) {
    return {
      maxDrawdown: { available: true, value: 0, displayBasisPoints: 0 },
      peakDate: null,
      troughDate: null,
      recoveryDate: null,
      recoveryDays: null,
      recoveryStatus: 'not_applicable',
    };
  }

  let peakIndex = 0;
  for (let index = 0; index <= troughIndex; index += 1) {
    if (values[index] === runningPeakAtTrough) peakIndex = index;
  }

  let recoveryIndex: number | null = null;
  for (let index = troughIndex; index < values.length; index += 1) {
    if (values[index] >= runningPeakAtTrough) {
      recoveryIndex = index;
      break;
    }
  }

  return {
    maxDrawdown: basisPointMetricAvailable(maxDrawdown),
    peakDate: dates[peakIndex],
    troughDate: dates[troughIndex],
    recoveryDate: recoveryIndex === null ? null : dates[recoveryIndex],
    recoveryDays: recoveryIndex === null ? null : civilDay(dates[recoveryIndex]) - civilDay(dates[troughIndex]),
    recoveryStatus: recoveryIndex === null ? 'not_recovered' : 'recovered',
  };
}

function validateAsset(asset: AssetSeriesArtifact): boolean {
  if (typeof asset.assetKey !== 'string' || !asset.assetKey) return false;
  if (!SUPPORTED_SERIES_BASES.includes(asset.seriesBasis as typeof SUPPORTED_SERIES_BASES[number])) return false;
  if (!Array.isArray(asset.dates) || !Array.isArray(asset.growthIndex) || asset.dates.length !== asset.growthIndex.length) {
    return false;
  }
  if (asset.dates.length === 0) return false;
  if (typeof asset.annualizationFactor !== 'number' || !Number.isFinite(asset.annualizationFactor) || asset.annualizationFactor <= 0) {
    return false;
  }
  let previous: string | null = null;
  for (let index = 0; index < asset.dates.length; index += 1) {
    const currentDate = asset.dates[index];
    const value = asset.growthIndex[index];
    if (!isValidCivilDate(currentDate)) return false;
    if (previous !== null && currentDate <= previous) return false;
    if (typeof value !== 'number' || !Number.isFinite(value) || value <= 0) return false;
    previous = currentDate;
  }
  return true;
}

function checkMethodology(assetA: AssetSeriesArtifact, assetB: AssetSeriesArtifact): boolean {
  return (
    assetA.schemaVersion === SUPPORTED_SCHEMA_VERSION &&
    assetB.schemaVersion === SUPPORTED_SCHEMA_VERSION &&
    assetA.methodologyVersion === SUPPORTED_METHODOLOGY_VERSION &&
    assetB.methodologyVersion === SUPPORTED_METHODOLOGY_VERSION &&
    SUPPORTED_SERIES_BASES.includes(assetA.seriesBasis as typeof SUPPORTED_SERIES_BASES[number]) &&
    SUPPORTED_SERIES_BASES.includes(assetB.seriesBasis as typeof SUPPORTED_SERIES_BASES[number])
  );
}

function dateToIndex(asset: AssetSeriesArtifact): Map<string, number> {
  return new Map(asset.dates.map((currentDate, index) => [currentDate, index]));
}

function nativeWindow(asset: AssetSeriesArtifact, effectiveStart: string, effectiveEnd: string) {
  const dates: string[] = [];
  const values: number[] = [];
  for (let index = 0; index < asset.dates.length; index += 1) {
    const currentDate = asset.dates[index];
    if (effectiveStart <= currentDate && currentDate <= effectiveEnd) {
      dates.push(currentDate);
      values.push(asset.growthIndex[index]);
    }
  }
  return { dates, values };
}

function assetMetrics(
  asset: AssetSeriesArtifact,
  dates: string[],
  values: number[],
  amountCents: number,
  elapsedDays: number
): AssetScenarioMetrics {
  const amountUsd = amountCents / 100;
  const growth = values[values.length - 1] / values[0];
  const endingValueUsd = amountUsd * growth;
  const endingValueCents = displayCents(endingValueUsd);
  const profitLossUsd = endingValueUsd - amountUsd;
  const profitLossCents = endingValueCents - amountCents;
  const totalReturnValue = growth - 1;
  const returns = simpleReturns(values);
  const drawdown = drawdownStats(values, dates);

  let cagr = basisPointMetricUnavailable('period_too_short');
  if (elapsedDays >= 30) {
    const cagrValue = growth ** (CAGR_DAY_COUNT / elapsedDays) - 1;
    cagr = basisPointMetricAvailable(cagrValue);
  }

  let volatility = basisPointMetricUnavailable('insufficient_data');
  if (returns.length >= 30) {
    const stddev = sampleStddev(returns);
    if (stddev !== null) {
      const volatilityValue = stddev * Math.sqrt(asset.annualizationFactor);
      volatility = basisPointMetricAvailable(volatilityValue);
    }
  }

  let calmar = hundredthsMetricUnavailable('period_too_short');
  const firstAnniversaryReached = dates[dates.length - 1] >= firstAnniversary(dates[0]);
  const drawdownMetric = drawdown.maxDrawdown;
  if (firstAnniversaryReached && cagr.available && drawdownMetric.available) {
    const maxDrawdown = drawdownMetric.value;
    if (Math.abs(maxDrawdown) >= CALMAR_MIN_ABS_DRAWDOWN) {
      const calmarValue = cagr.value / Math.abs(maxDrawdown);
      calmar = hundredthsMetricAvailable(calmarValue);
    } else {
      calmar = hundredthsMetricUnavailable('zero_drawdown');
    }
  }

  return {
    endingValueUsd: normalizeZero(endingValueUsd),
    endingValueCents,
    profitLossUsd: normalizeZero(profitLossUsd),
    profitLossCents,
    totalReturn: basisPointMetricAvailable(totalReturnValue),
    cagr,
    volatility,
    drawdown,
    calmar,
    nativeObservationCount: values.length,
    nativeReturnCount: returns.length,
    periodOutcome: profitLossCents > 0 ? 'gain' : profitLossCents < 0 ? 'loss' : 'unchanged',
  };
}

function compareDisplayValues(
  metricA: BasisPointMetricValue,
  metricB: BasisPointMetricValue
): ComparisonWinner {
  if (!metricA.available || !metricB.available) return 'unavailable';
  const valueA = metricA.displayBasisPoints;
  const valueB = metricB.displayBasisPoints;
  if (valueA === valueB) return 'tie';
  return valueA > valueB ? 'asset_a' : 'asset_b';
}

function compareEndingValue(metricsA: AssetScenarioMetrics, metricsB: AssetScenarioMetrics): ComparisonWinner {
  if (metricsA.endingValueCents === metricsB.endingValueCents) return 'tie';
  return metricsA.endingValueCents > metricsB.endingValueCents ? 'asset_a' : 'asset_b';
}

function compareDeeperDrawdown(metricsA: AssetScenarioMetrics, metricsB: AssetScenarioMetrics): ComparisonWinner {
  const drawdownA = metricsA.drawdown.maxDrawdown;
  const drawdownB = metricsB.drawdown.maxDrawdown;
  if (!drawdownA.available || !drawdownB.available) return 'unavailable';
  const valueA = drawdownA.displayBasisPoints;
  const valueB = drawdownB.displayBasisPoints;
  if (typeof valueA !== 'number' || typeof valueB !== 'number') return 'unavailable';
  if (valueA === valueB) return 'tie';
  return valueA < valueB ? 'asset_a' : 'asset_b';
}

export function calculateScenario(input: ScenarioInput): ScenarioResult {
  if (!input || typeof input !== 'object') throw new Error('invalid scenario input');

  const { assetA, assetB, amountCents, requestedStart, requestedEnd } = input;
  if (!assetA || typeof assetA !== 'object' || !assetB || typeof assetB !== 'object') {
    throw new Error('invalid asset artifact');
  }
  if (
    typeof assetA.assetKey !== 'string' ||
    !assetA.assetKey ||
    typeof assetB.assetKey !== 'string' ||
    !assetB.assetKey
  ) {
    throw new Error('invalid asset artifact');
  }
  if (assetA.assetKey === assetB.assetKey) return { status: 'error', reason: 'same_asset' };
  if (!Number.isSafeInteger(amountCents) || amountCents < MIN_AMOUNT_CENTS || amountCents > MAX_AMOUNT_CENTS) {
    return { status: 'error', reason: 'invalid_amount' };
  }
  if (!isValidCivilDate(requestedStart) || !isValidCivilDate(requestedEnd)) {
    return { status: 'error', reason: 'invalid_date' };
  }
  if (requestedStart > requestedEnd) return { status: 'error', reason: 'start_after_end' };
  if (!checkMethodology(assetA, assetB)) return { status: 'error', reason: 'methodology_mismatch' };
  if (!validateAsset(assetA) || !validateAsset(assetB)) throw new Error('invalid asset artifact');

  const indexA = dateToIndex(assetA);
  const indexB = dateToIndex(assetB);
  const sharedDates = assetA.dates.filter((currentDate) => indexB.has(currentDate));
  if (!sharedDates.length) return { status: 'error', reason: 'no_overlap' };

  const requestedSharedDates = sharedDates.filter((currentDate) => requestedStart <= currentDate && currentDate <= requestedEnd);
  if (!requestedSharedDates.length) return { status: 'error', reason: 'no_overlap' };

  const effectiveStart = sharedDates.find((currentDate) => currentDate >= requestedStart) || null;
  const effectiveEnd = [...sharedDates].reverse().find((currentDate) => currentDate <= requestedEnd) || null;
  if (effectiveStart === null || effectiveEnd === null || effectiveStart >= effectiveEnd) {
    return { status: 'error', reason: 'insufficient_shared_observations' };
  }

  const selectedSharedDates = sharedDates.filter((currentDate) => effectiveStart <= currentDate && currentDate <= effectiveEnd);
  if (selectedSharedDates.length < 2) return { status: 'error', reason: 'insufficient_shared_observations' };

  const elapsedDays = civilDay(effectiveEnd) - civilDay(effectiveStart);
  if (elapsedDays <= 0) return { status: 'error', reason: 'insufficient_shared_observations' };

  const nativeA = nativeWindow(assetA, effectiveStart, effectiveEnd);
  const nativeB = nativeWindow(assetB, effectiveStart, effectiveEnd);
  const sharedValuesA = selectedSharedDates.map((currentDate) => assetA.growthIndex[indexA.get(currentDate) as number]);
  const sharedValuesB = selectedSharedDates.map((currentDate) => assetB.growthIndex[indexB.get(currentDate) as number]);
  const metricsA = assetMetrics(assetA, nativeA.dates, nativeA.values, amountCents, elapsedDays);
  const metricsB = assetMetrics(assetB, nativeB.dates, nativeB.values, amountCents, elapsedDays);
  const sharedReturnsA = simpleReturns(sharedValuesA);
  const sharedReturnsB = simpleReturns(sharedValuesB);
  const correlation =
    sharedReturnsA.length >= 30 && sharedReturnsB.length >= 30
      ? pearsonCorrelation(sharedReturnsA, sharedReturnsB)
      : hundredthsMetricUnavailable('insufficient_data');
  const amountUsd = amountCents / 100;

  return {
    status: 'ok',
    scenario: {
      methodologyVersion: SUPPORTED_METHODOLOGY_VERSION,
      methodologyContractHash: METHODOLOGY_HASH,
      amountCents,
      requestedStart,
      requestedEnd,
      effectiveStart,
      effectiveEnd,
      startSnap: effectiveStart === requestedStart ? 'exact' : 'forward',
      endSnap: effectiveEnd === requestedEnd ? 'exact' : 'backward',
      elapsedDays,
      sharedObservationCount: selectedSharedDates.length,
      assetA: metricsA,
      assetB: metricsB,
      pair: {
        correlation,
        sharedReturnCount: sharedReturnsA.length,
      },
      wealthPath: selectedSharedDates.map((currentDate) => ({
        date: currentDate,
        assetAUsd: normalizeZero(amountUsd * assetA.growthIndex[indexA.get(currentDate) as number] / sharedValuesA[0]),
        assetBUsd: normalizeZero(amountUsd * assetB.growthIndex[indexB.get(currentDate) as number] / sharedValuesB[0]),
      })),
      endingValueWinner: compareEndingValue(metricsA, metricsB),
      totalReturnWinner: compareDisplayValues(metricsA.totalReturn, metricsB.totalReturn),
      deeperDrawdownAsset: compareDeeperDrawdown(metricsA, metricsB),
    },
  };
}
