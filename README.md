# return-scenario-engine

Dependency-free historical investment scenarios for caller-owned normalized index
series. [Gale Finance Compare Lab](https://www.gale.finance/calculator/) uses
`return-scenario-engine@0.1.0` for its historical calculations. TypeScript and
Python share a public contract and synthetic golden corpus.

![Gale Finance Compare Lab: a $1,000 BTC versus gold result](https://raw.githubusercontent.com/sidko/return-scenario-engine/main/docs/assets/gale-compare-lab.jpg)

Captured September 10, 2026: a public $1,000 BTC versus gold calculation for
September 9, 2025 through September 9, 2026. The result cards show $698.77 and
$1,213.96. The [reproducible public scenario](https://www.gale.finance/calculator/#cl=v1&a=btc&b=xau&c=100000&s=2025-09-09&e=2026-09-09)
uses Gale Compare Lab, powered by this library's historical calculations.

```bash
npm install return-scenario-engine
# or: python -m pip install return-scenario-engine
```

```ts
import { calculateScenario } from 'return-scenario-engine';

const dates = ['2024-01-01', '2024-01-02', '2024-01-03'];
const result = calculateScenario({
  amountCents: 100_000,
  requestedStart: '2024-01-01',
  requestedEnd: '2024-01-03',
  assetA: { assetKey: 'sample-a', schemaVersion: 1, methodologyVersion: 'return-scenario-v1.0.0', seriesBasis: 'close_index', annualizationFactor: 365, dates, growthIndex: [100, 110, 121] },
  assetB: { assetKey: 'sample-b', schemaVersion: 1, methodologyVersion: 'return-scenario-v1.0.0', seriesBasis: 'close_index', annualizationFactor: 365, dates, growthIndex: [100, 95, 100] },
});

console.log(result.status); // "ok"
```

Each artifact provides its key, schema/methodology versions, series basis, annualization factor, ordered civil dates, and positive normalized index values. Results contain snapped dates, integer-cent ending values, display-rounded metrics, drawdown/recovery data, correlation, and a shared wealth path; invalid inputs return named errors.

`roundHalfAwayFromZero` / `round_half_away_from_zero` accept any positive safe
integer scale and reject nonfinite values, invalid scales, and unsafe results.

![Reproducible synthetic financial scenario result](https://raw.githubusercontent.com/sidko/return-scenario-engine/main/docs/assets/synthetic-scenario.svg)

Output from the reproducible synthetic `crypto_crypto_long_window` fixture: a
$1,000 scenario ends at $2,309.81 for asset A and $845.66 for asset B.

## Contract and limits

Node.js 20+ and Python 3.11+ are supported. Both `0.1.0` artifacts share the methodology JSON, public SHA-256 hash, and synthetic fixtures. Read [`return-scenario-v1.json`](https://github.com/sidko/return-scenario-engine/blob/main/methodology/return-scenario-v1.json) before comparing outputs. The package does not fetch prices, select assets, retain provider data, or implement routes and UI. The `0.1.0` npm and PyPI artifacts are immutable.

## Development

```bash
npm ci
python -m pip install -e './python[test]'
PYTHON_BIN=python3 npm test
python -m build python
```

`npm test` builds a temporary Python wheel and checks every golden scenario against both implementations. Fixtures are synthetic and contain no provider history.

## First release

For the first npm release, publish the reviewed tarball interactively with 2FA
and configure npm trusted publishing for `.github/workflows/release.yml` and
its `npm` environment. Configure PyPI's pending trusted publisher, then run the
manual release workflow against the existing tag with target `pypi` to upload
the matching Python artifact. Verify both registries before creating the GitHub
Release. Later releases use the same manual workflow with target `both`; retry a
single failed side with `npm` or `pypi`. Never republish an immutable existing
version or treat a mismatched pair as successful.

## Origin

Gale Finance uses `return-scenario-engine@0.1.0` for the historical calculations in
[Compare Lab](https://www.gale.finance/calculator/). Gale’s launch-bundle
formats, UI, routes, analytics, market data, and asset policy stay private.

Early commits reconstruct private-monorepo milestones. Author dates reflect original work; public content and hashes were rewritten to exclude private details. Some early development used Claude as a coding assistant; Sid Kalla selected, reviewed, and maintains this code.

Apache-2.0 covers this code and does not grant rights to Gale Finance branding. See [CONTRIBUTING](https://github.com/sidko/return-scenario-engine/blob/main/CONTRIBUTING.md), [SECURITY](https://github.com/sidko/return-scenario-engine/blob/main/SECURITY.md), and [AGENT_INTEGRATION](https://github.com/sidko/return-scenario-engine/blob/main/AGENT_INTEGRATION.md).

Maintenance is best effort; the latest release is supported unless its notes say otherwise.
