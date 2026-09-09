# return-scenario-engine

Dependency-free historical investment scenarios for caller-owned normalized index series. TypeScript and Python share a public contract and synthetic golden corpus.

![Synthetic scenario result](https://raw.githubusercontent.com/sidko/return-scenario-engine/main/docs/assets/synthetic-scenario.svg)

```bash
npm install return-scenario-engine
# or: python -m pip install return-scenario-engine
```

```ts
import { calculateScenario } from 'return-scenario-engine';

const result = calculateScenario({ amountCents, requestedStart, requestedEnd, assetA, assetB });
```

Each artifact provides its key, schema/methodology versions, series basis, annualization factor, ordered civil dates, and positive normalized index values. Results contain snapped dates, integer-cent ending values, display-rounded metrics, drawdown/recovery data, correlation, and a shared wealth path; invalid inputs return named errors.

The visual is actual output from the synthetic `crypto_crypto_long_window` golden case: a $1,000 scenario ends at $2,309.81 for asset A and $845.66 for asset B. This is a headless library, not a chart UI.

## Contract and limits

Node.js 20+ and Python 3.11+ are supported. Both `0.1.0` artifacts share the methodology JSON, public SHA-256 hash, and synthetic fixtures. Read [`return-scenario-v1.json`](https://github.com/sidko/return-scenario-engine/blob/main/methodology/return-scenario-v1.json) before comparing outputs. The package does not fetch prices, select assets, retain provider data, or implement routes and UI. A partial paired registry upload must be completed or corrected before announcing the version.

## Development

```bash
npm ci
PYTHON_BIN=python3 npm test
python -m pip install -e './python[test]'
python -m build python
```

`npm test` builds a temporary Python wheel and checks every golden scenario against both implementations. Fixtures are synthetic and contain no provider history.

## Origin

This package was extracted from [Gale Finance](https://gale.finance/) calculation work. Gale’s launch-bundle formats, UI, routes, analytics, market data, and asset policy stay private. Until migration, it is “extracted from Gale,” not evidence that Gale uses the published artifact.

Early commits reconstruct private-monorepo milestones. Author dates reflect original work; public content and hashes were rewritten to exclude private details. Some early development used Claude as a coding assistant; Sid Kalla selected, reviewed, and maintains this code.

Apache-2.0 covers this code and does not grant rights to Gale Finance branding. See [CONTRIBUTING](https://github.com/sidko/return-scenario-engine/blob/main/CONTRIBUTING.md), [SECURITY](https://github.com/sidko/return-scenario-engine/blob/main/SECURITY.md), and [AGENT_INTEGRATION](https://github.com/sidko/return-scenario-engine/blob/main/AGENT_INTEGRATION.md).
