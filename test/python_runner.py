import json
import sys
from return_scenario_engine import calculate_scenario, display_basis_points, display_cents, display_hundredths, first_anniversary, parse_amount_to_cents, pearson_correlation, round_half_away_from_zero

payload = json.load(sys.stdin)
if payload["operation"] == "scenario":
    print(json.dumps(calculate_scenario(payload["input"]), allow_nan=False))
elif payload["operation"] == "scalar":
    operation = payload["name"]
    if operation == "display_cents": result = display_cents(payload["input"])
    elif operation == "display_basis_points": result = display_basis_points(payload["input"])
    elif operation == "display_hundredths": result = display_hundredths(payload["input"])
    elif operation == "round_half_away_from_zero": result = round_half_away_from_zero(payload["input"])
    elif operation == "first_anniversary": result = first_anniversary(payload["input"])
    elif operation == "pearson_correlation": result = pearson_correlation(*payload["input"])
    else: raise ValueError(f"unknown scalar operation: {operation}")
    print(json.dumps(result, allow_nan=False))
else:
    print(json.dumps(parse_amount_to_cents(payload["input"])))
