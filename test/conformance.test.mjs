import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import test from 'node:test';
import { ARTIFACT_SCHEMA_VERSION, METHODOLOGY_HASH, METHODOLOGY_VERSION, calculateScenario, displayBasisPoints, displayCents, displayHundredths, firstAnniversary, parseAmountToCents, pearsonCorrelation, roundHalfAwayFromZero } from '../lib/index.js';

const fixture = JSON.parse(readFileSync(new URL('../fixtures/golden-v1.json', import.meta.url)));
const python = process.env.PYTHON ?? 'python3';
const pythonPath = process.env.RETURN_SCENARIO_ENGINE_PYTHONPATH ?? new URL('../python', import.meta.url).pathname;
function runPython(payload) {
  const result = spawnSync(python, ['test/python_runner.py'], { input: JSON.stringify(payload), encoding: 'utf8', env: { ...process.env, PYTHONPATH: pythonPath } });
  assert.equal(result.status, 0, result.stderr);
  return JSON.parse(result.stdout);
}
function equalContract(actual, expected, path = '$') {
  if (typeof expected === 'number') {
    assert.equal(typeof actual, 'number', path);
    if (/(displayBasisPoints|displayHundredths|Cents|Count|Days|elapsedDays|schemaVersion)$/.test(path)) {
      assert.equal(actual, expected, path);
      return;
    }
    const absolute = path.includes('Usd') ? 1e-8 : 1e-12;
    const relative = path.includes('Usd') ? 1e-12 : 1e-10;
    assert.ok(Math.abs(actual - expected) <= Math.max(absolute, Math.abs(expected) * relative), `${path}: ${actual} !== ${expected}`);
  } else if (Array.isArray(expected)) {
    assert.equal(actual.length, expected.length, path);
    expected.forEach((value, index) => equalContract(actual[index], value, `${path}[${index}]`));
  } else if (expected && typeof expected === 'object') {
    assert.deepEqual(Object.keys(actual).sort(), Object.keys(expected).sort(), `${path} keys`);
    Object.entries(expected).forEach(([key, value]) => equalContract(actual[key], value, `${path}.${key}`));
  } else assert.equal(actual, expected, path);
}

test('full sanitized synthetic golden corpus conforms in TypeScript and Python', () => {
  assert.equal(fixture.provenance.providerHistoryIncluded, false);
  assert.equal(fixture.scenarioCases.length, 31);
  for (const current of fixture.scenarioCases) {
    const ts = calculateScenario(current.input);
    const py = runPython({ operation: 'scenario', input: current.input });
    equalContract(ts, current.expected, current.id);
    equalContract(py, current.expected, current.id);
  }
  for (const current of fixture.parserCases) {
    equalContract(parseAmountToCents(current.input), current.expected, `parser:${String(current.input)}`);
    equalContract(runPython({ operation: 'amount', input: current.input }), current.expected, `python parser:${String(current.input)}`);
  }
});

test('canonical methodology bytes, constants, and golden fixture share one hash', () => {
  const tsMethodology = readFileSync(new URL('../methodology/return-scenario-v1.json', import.meta.url));
  const pythonMethodology = readFileSync(new URL('../python/return_scenario_engine/methodology/return-scenario-v1.json', import.meta.url));
  const hash = createHash('sha256').update(tsMethodology).digest('hex');
  assert.deepEqual(pythonMethodology, tsMethodology);
  assert.equal(hash, METHODOLOGY_HASH);
  assert.equal(fixture.methodologyContractHash, hash);
  assert.equal(fixture.methodologyVersion, METHODOLOGY_VERSION);
  assert.equal(JSON.parse(tsMethodology).schemaVersion, ARTIFACT_SCHEMA_VERSION);
  const pythonSource = readFileSync(new URL('../python/return_scenario_engine/__init__.py', import.meta.url), 'utf8');
  assert.match(pythonSource, new RegExp(`METHODOLOGY_HASH = "${hash}"`));
});

test('scalar anchors retain display rounding, leap-day, and correlation semantics', () => {
  const { rounding, dates, correlation } = fixture.scalarAnchors;
  assert.equal(displayCents(1.005), rounding.centsPositiveHalf);
  assert.equal(runPython({ operation: 'scalar', name: 'display_cents', input: 1.005 }), rounding.centsPositiveHalf);
  assert.equal(displayBasisPoints(-0.00005), rounding.basisPointsNegativeHalf);
  assert.equal(runPython({ operation: 'scalar', name: 'display_basis_points', input: -0.00005 }), rounding.basisPointsNegativeHalf);
  assert.equal(displayBasisPoints(0.00005), rounding.basisPointsPositiveHalf);
  assert.equal(displayHundredths(-1.235), rounding.hundredthsNegativeHalf);
  assert.equal(displayHundredths(1.235), rounding.hundredthsPositiveHalf);
  assert.equal(runPython({ operation: 'scalar', name: 'display_hundredths', input: 1.235 }), rounding.hundredthsPositiveHalf);
  assert.equal(roundHalfAwayFromZero(-0), rounding.directNegativeZero);
  assert.equal(firstAnniversary('2024-02-29'), dates.february29FirstAnniversary);
  assert.equal(runPython({ operation: 'scalar', name: 'first_anniversary', input: '2024-02-29' }), dates.february29FirstAnniversary);
  equalContract(pearsonCorrelation([1, 2, 3], [2, 4, 6]), correlation.identicalNonconstant);
  equalContract(runPython({ operation: 'scalar', name: 'pearson_correlation', input: [[1, 2, 3], [2, 4, 6]] }), correlation.identicalNonconstant);
  equalContract(pearsonCorrelation([1, 1, 1], [2, 3, 4]), correlation.zeroVariance);
});

test('golden comparator detects a deliberate displayed-money mutation', () => {
  const current = fixture.scenarioCases.find((item) => item.id === 'crypto_crypto_long_window');
  assert.ok(current?.expected.status === 'ok');
  const mutated = structuredClone(current.expected);
  mutated.scenario.assetA.endingValueCents += 1;
  assert.throws(() => equalContract(calculateScenario(current.input), mutated, 'deliberateMutation'));
});
