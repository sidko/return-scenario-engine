# return-scenario-engine (Python)

The Python distribution provides the same dependency-free normalized-index
scenario API, methodology JSON, public SHA-256 hash, and synthetic golden corpus
as the TypeScript package. Install with `python -m pip install
return-scenario-engine`, then call `calculate_scenario` with explicit artifact
dictionaries. Full contract, limits, examples, and security guidance are in the
[repository README](https://github.com/sidko/return-scenario-engine#readme).

```python
from return_scenario_engine import calculate_scenario

dates = ["2024-01-01", "2024-01-02", "2024-01-03"]
base = {"schemaVersion": 1, "methodologyVersion": "return-scenario-v1.0.0", "seriesBasis": "close_index", "annualizationFactor": 365, "dates": dates}
result = calculate_scenario({"amountCents": 100_000, "requestedStart": dates[0], "requestedEnd": dates[-1], "assetA": base | {"assetKey": "sample-a", "growthIndex": [100, 110, 121]}, "assetB": base | {"assetKey": "sample-b", "growthIndex": [100, 95, 100]}})
assert result["status"] == "ok"
```
