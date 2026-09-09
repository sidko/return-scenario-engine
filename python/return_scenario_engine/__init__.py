"""Portable public return-scenario calculations for normalized index artifacts."""

from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
import math
import re
from typing import Any


ARTIFACT_SCHEMA_VERSION = 1
METHODOLOGY_VERSION = "return-scenario-v1.0.0"
METHODOLOGY_HASH = "55ef9001eb8795071cfff1e135430d41952aedd8708ba1d767c3453804fd49b0"
SUPPORTED_SERIES_BASES = frozenset({"close_index", "adjusted_close_index"})
DEFAULT_FIXTURE_SERIES_BASIS = "close_index"

MIN_AMOUNT_CENTS = 100
MAX_AMOUNT_CENTS = 1_000_000_000
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
CAGR_DAY_COUNT = 365.25
CALMAR_MIN_ABS_DRAWDOWN = 0.0001
ZERO_VARIANCE_SUMSQ_EPSILON = 1e-24
CORRELATION_CLAMP_TOLERANCE = 1e-12


def metric_available(value: float, display: dict[str, Any] | None = None) -> dict[str, Any]:
    if not math.isfinite(value):
        return metric_unavailable("nonfinite_result")
    output: dict[str, Any] = {"available": True, "value": normalize_zero(value)}
    if display:
        output.update(display)
    return output


def metric_unavailable(reason: str) -> dict[str, Any]:
    return {"available": False, "reason": reason}


def normalize_zero(value: float) -> float:
    return 0.0 if value == 0 else value


def round_half_away_from_zero(value: float, scale: int = 1) -> int:
    if not math.isfinite(value):
        raise ValueError("cannot round nonfinite value")
    sign = -1 if value < 0 else 1
    rounded = (Decimal(str(abs(value))) * Decimal(scale)).to_integral_value(rounding=ROUND_HALF_UP)
    return sign * int(rounded)


def display_cents(usd_value: float) -> int:
    return round_half_away_from_zero(usd_value, 100)


def display_basis_points(decimal_value: float) -> int:
    return round_half_away_from_zero(decimal_value, 10_000)


def display_hundredths(ratio_value: float) -> int:
    return round_half_away_from_zero(ratio_value, 100)


def is_valid_civil_date(value: str) -> bool:
    if not isinstance(value, str) or not DATE_RE.match(value):
        return False
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return False
    return parsed.isoformat() == value


def parse_civil_date(value: str) -> date:
    if not is_valid_civil_date(value):
        raise ValueError(f"invalid civil date: {value}")
    return date.fromisoformat(value)


def civil_day(value: str) -> int:
    return parse_civil_date(value).toordinal()


def first_anniversary(value: str) -> str:
    parsed = parse_civil_date(value)
    try:
        anniversary = parsed.replace(year=parsed.year + 1)
    except ValueError:
        anniversary = date(parsed.year + 1, 2, 28)
    return anniversary.isoformat()


def parse_usd_amount_to_cents(value: str) -> dict[str, Any]:
    if not isinstance(value, str):
        return {"ok": False, "reason": "invalid_amount"}
    raw = re.sub(r"^\$\s*", "", value.strip())
    plain_amount = re.compile(r"^(0|[1-9][0-9]*)(\.[0-9]{1,2})?$")
    grouped_amount = re.compile(r"^(0|[1-9][0-9]{0,2}(,[0-9]{3})+)(\.[0-9]{1,2})?$")
    if not plain_amount.match(raw) and not grouped_amount.match(raw):
        return {"ok": False, "reason": "invalid_amount"}
    dollars, _, cents = raw.replace(",", "").partition(".")
    parsed = int(dollars) * 100 + int(cents.ljust(2, "0") or "0")
    if parsed < MIN_AMOUNT_CENTS or parsed > MAX_AMOUNT_CENTS:
        return {"ok": False, "reason": "invalid_amount"}
    return {"ok": True, "cents": parsed}


parse_amount_to_cents = parse_usd_amount_to_cents


def ordered_mean(values: list[float]) -> float:
    return sum(values) / len(values)


def sample_variance(values: list[float]) -> float | None:
    if len(values) < 2:
        return None
    mean = ordered_mean(values)
    return sum((value - mean) ** 2 for value in values) / (len(values) - 1)


def sample_stddev(values: list[float]) -> float | None:
    variance = sample_variance(values)
    return math.sqrt(variance) if variance is not None else None


def simple_returns(values: list[float]) -> list[float]:
    returns: list[float] = []
    for index in range(1, len(values)):
        previous = values[index - 1]
        current = values[index]
        if previous <= 0 or current <= 0:
            raise ValueError("normalized indexes must be positive")
        returns.append(current / previous - 1)
    return returns


def asset_values(asset: dict[str, Any]) -> list[Any]:
    return asset.get("growthIndex")


def pearson_correlation(values_a: list[float], values_b: list[float]) -> dict[str, Any]:
    if len(values_a) != len(values_b) or len(values_a) < 2:
        return metric_unavailable("insufficient_data")

    mean_a = ordered_mean(values_a)
    mean_b = ordered_mean(values_b)
    covariance = 0.0
    sum_sq_a = 0.0
    sum_sq_b = 0.0
    for value_a, value_b in zip(values_a, values_b):
        delta_a = value_a - mean_a
        delta_b = value_b - mean_b
        covariance += delta_a * delta_b
        sum_sq_a += delta_a * delta_a
        sum_sq_b += delta_b * delta_b

    if sum_sq_a <= ZERO_VARIANCE_SUMSQ_EPSILON or sum_sq_b <= ZERO_VARIANCE_SUMSQ_EPSILON:
        return metric_unavailable("zero_variance")

    correlation = covariance / math.sqrt(sum_sq_a * sum_sq_b)
    if abs(abs(correlation) - 1) <= CORRELATION_CLAMP_TOLERANCE:
        correlation = 1.0 if correlation > 0 else -1.0
    elif correlation < -1 or correlation > 1:
        return metric_unavailable("nonfinite_result")
    return metric_available(correlation, {"displayHundredths": display_hundredths(correlation)})


def drawdown_stats(values: list[float], dates: list[str]) -> dict[str, Any]:
    if len(values) < 2:
        return {
            "maxDrawdown": metric_unavailable("insufficient_data"),
            "peakDate": None,
            "troughDate": None,
            "recoveryDate": None,
            "recoveryDays": None,
            "recoveryStatus": "not_applicable",
        }

    running_peak = values[0]
    running_peak_at_trough = values[0]
    trough_index = 0
    max_drawdown = 0.0

    for index, value in enumerate(values):
        if value >= running_peak:
            running_peak = value
        drawdown = value / running_peak - 1
        if drawdown < max_drawdown:
            max_drawdown = drawdown
            trough_index = index
            running_peak_at_trough = running_peak

    if max_drawdown == 0:
        return {
            "maxDrawdown": metric_available(0.0, {"displayBasisPoints": 0}),
            "peakDate": None,
            "troughDate": None,
            "recoveryDate": None,
            "recoveryDays": None,
            "recoveryStatus": "not_applicable",
        }

    peak_index = 0
    for index in range(0, trough_index + 1):
        if values[index] == running_peak_at_trough:
            peak_index = index

    recovery_index = None
    for index in range(trough_index, len(values)):
        if values[index] >= running_peak_at_trough:
            recovery_index = index
            break

    return {
        "maxDrawdown": metric_available(max_drawdown, {"displayBasisPoints": display_basis_points(max_drawdown)}),
        "peakDate": dates[peak_index],
        "troughDate": dates[trough_index],
        "recoveryDate": dates[recovery_index] if recovery_index is not None else None,
        "recoveryDays": civil_day(dates[recovery_index]) - civil_day(dates[trough_index]) if recovery_index is not None else None,
        "recoveryStatus": "recovered" if recovery_index is not None else "not_recovered",
    }


def validate_asset(asset: dict[str, Any]) -> bool:
    asset_key = asset.get("assetKey")
    if not isinstance(asset_key, str) or not asset_key:
        return False
    series_basis = asset.get("seriesBasis")
    if series_basis not in SUPPORTED_SERIES_BASES:
        return False
    dates = asset.get("dates")
    values = asset_values(asset)
    if not isinstance(dates, list) or not isinstance(values, list) or len(dates) != len(values):
        return False
    if not dates:
        return False
    annualization_factor = asset.get("annualizationFactor")
    if (
        isinstance(annualization_factor, bool)
        or not isinstance(annualization_factor, (int, float))
        or not math.isfinite(annualization_factor)
        or annualization_factor <= 0
    ):
        return False
    previous = None
    for current_date, value in zip(dates, values):
        if not is_valid_civil_date(current_date):
            return False
        if previous is not None and current_date <= previous:
            return False
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
            return False
        previous = current_date
    return True


def check_methodology(asset_a: dict[str, Any], asset_b: dict[str, Any]) -> bool:
    return (
        asset_a.get("schemaVersion") == ARTIFACT_SCHEMA_VERSION
        and asset_b.get("schemaVersion") == ARTIFACT_SCHEMA_VERSION
        and asset_a.get("methodologyVersion") == METHODOLOGY_VERSION
        and asset_b.get("methodologyVersion") == METHODOLOGY_VERSION
        and asset_a.get("seriesBasis") in SUPPORTED_SERIES_BASES
        and asset_b.get("seriesBasis") in SUPPORTED_SERIES_BASES
    )


def date_to_index(asset: dict[str, Any]) -> dict[str, int]:
    return {current_date: index for index, current_date in enumerate(asset["dates"])}


def native_window(asset: dict[str, Any], effective_start: str, effective_end: str) -> tuple[list[str], list[float]]:
    dates: list[str] = []
    values: list[float] = []
    for current_date, value in zip(asset["dates"], asset_values(asset)):
        if effective_start <= current_date <= effective_end:
            dates.append(current_date)
            values.append(float(value))
    return dates, values


def asset_metrics(asset: dict[str, Any], dates: list[str], values: list[float], amount_cents: int, elapsed_days: int) -> dict[str, Any]:
    amount_usd = amount_cents / 100
    growth = values[-1] / values[0]
    ending_value_usd = amount_usd * growth
    ending_value_cents = display_cents(ending_value_usd)
    profit_loss_usd = ending_value_usd - amount_usd
    profit_loss_cents = ending_value_cents - amount_cents
    total_return = growth - 1
    returns = simple_returns(values)
    drawdown = drawdown_stats(values, dates)

    cagr = metric_unavailable("period_too_short")
    if elapsed_days >= 30:
        cagr_value = growth ** (CAGR_DAY_COUNT / elapsed_days) - 1
        cagr = metric_available(cagr_value, {"displayBasisPoints": display_basis_points(cagr_value)})

    volatility = metric_unavailable("insufficient_data")
    if len(returns) >= 30:
        stddev = sample_stddev(returns)
        if stddev is not None:
            volatility_value = stddev * math.sqrt(float(asset.get("annualizationFactor", 252)))
            volatility = metric_available(volatility_value, {"displayBasisPoints": display_basis_points(volatility_value)})

    calmar = metric_unavailable("period_too_short")
    drawdown_metric = drawdown["maxDrawdown"]
    first_anniversary_reached = dates[-1] >= first_anniversary(dates[0])
    if first_anniversary_reached and cagr["available"] and drawdown_metric["available"]:
        max_drawdown = drawdown_metric["value"]
        if abs(max_drawdown) >= CALMAR_MIN_ABS_DRAWDOWN:
            calmar_value = cagr["value"] / abs(max_drawdown)
            calmar = metric_available(calmar_value, {"displayHundredths": display_hundredths(calmar_value)})
        else:
            calmar = metric_unavailable("zero_drawdown")

    return {
        "endingValueUsd": normalize_zero(ending_value_usd),
        "endingValueCents": ending_value_cents,
        "profitLossUsd": normalize_zero(profit_loss_usd),
        "profitLossCents": profit_loss_cents,
        "totalReturn": metric_available(total_return, {"displayBasisPoints": display_basis_points(total_return)}),
        "cagr": cagr,
        "volatility": volatility,
        "drawdown": drawdown,
        "calmar": calmar,
        "nativeObservationCount": len(values),
        "nativeReturnCount": len(returns),
        "periodOutcome": "gain" if profit_loss_cents > 0 else "loss" if profit_loss_cents < 0 else "unchanged",
    }


def compare_display_values(metric_a: dict[str, Any], metric_b: dict[str, Any], display_key: str) -> str:
    if not metric_a.get("available") or not metric_b.get("available"):
        return "unavailable"
    value_a = metric_a[display_key]
    value_b = metric_b[display_key]
    if value_a == value_b:
        return "tie"
    return "asset_a" if value_a > value_b else "asset_b"


def compare_ending_value(metrics_a: dict[str, Any], metrics_b: dict[str, Any]) -> str:
    value_a = metrics_a["endingValueCents"]
    value_b = metrics_b["endingValueCents"]
    if value_a == value_b:
        return "tie"
    return "asset_a" if value_a > value_b else "asset_b"


def compare_deeper_drawdown(metrics_a: dict[str, Any], metrics_b: dict[str, Any]) -> str:
    drawdown_a = metrics_a["drawdown"]["maxDrawdown"]
    drawdown_b = metrics_b["drawdown"]["maxDrawdown"]
    if not drawdown_a.get("available") or not drawdown_b.get("available"):
        return "unavailable"
    value_a = drawdown_a["displayBasisPoints"]
    value_b = drawdown_b["displayBasisPoints"]
    if value_a == value_b:
        return "tie"
    return "asset_a" if value_a < value_b else "asset_b"


def calculate_scenario(input_payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(input_payload, dict):
        raise ValueError("invalid scenario input")

    asset_a = input_payload.get("assetA")
    asset_b = input_payload.get("assetB")
    amount_cents = input_payload.get("amountCents")
    requested_start = input_payload.get("requestedStart")
    requested_end = input_payload.get("requestedEnd")

    if not isinstance(asset_a, dict) or not isinstance(asset_b, dict):
        raise ValueError("invalid asset artifact")
    asset_key_a = asset_a.get("assetKey")
    asset_key_b = asset_b.get("assetKey")
    if not isinstance(asset_key_a, str) or not asset_key_a or not isinstance(asset_key_b, str) or not asset_key_b:
        raise ValueError("invalid asset artifact")
    if asset_key_a == asset_key_b:
        return {"status": "error", "reason": "same_asset"}
    if isinstance(amount_cents, bool) or not isinstance(amount_cents, int) or amount_cents < MIN_AMOUNT_CENTS or amount_cents > MAX_AMOUNT_CENTS:
        return {"status": "error", "reason": "invalid_amount"}
    if not is_valid_civil_date(requested_start) or not is_valid_civil_date(requested_end):
        return {"status": "error", "reason": "invalid_date"}
    if requested_start > requested_end:
        return {"status": "error", "reason": "start_after_end"}
    if not check_methodology(asset_a, asset_b):
        return {"status": "error", "reason": "methodology_mismatch"}
    if not validate_asset(asset_a) or not validate_asset(asset_b):
        raise ValueError("invalid asset artifact")

    index_a = date_to_index(asset_a)
    index_b = date_to_index(asset_b)
    shared_dates = [current_date for current_date in asset_a["dates"] if current_date in index_b]
    if not shared_dates:
        return {"status": "error", "reason": "no_overlap"}

    requested_shared_dates = [current_date for current_date in shared_dates if requested_start <= current_date <= requested_end]
    if not requested_shared_dates:
        return {"status": "error", "reason": "no_overlap"}

    effective_start = next((current_date for current_date in shared_dates if current_date >= requested_start), None)
    effective_end = next((current_date for current_date in reversed(shared_dates) if current_date <= requested_end), None)
    if effective_start is None or effective_end is None or effective_start >= effective_end:
        return {"status": "error", "reason": "insufficient_shared_observations"}

    selected_shared_dates = [current_date for current_date in shared_dates if effective_start <= current_date <= effective_end]
    if len(selected_shared_dates) < 2:
        return {"status": "error", "reason": "insufficient_shared_observations"}

    elapsed_days = civil_day(effective_end) - civil_day(effective_start)
    if elapsed_days <= 0:
        return {"status": "error", "reason": "insufficient_shared_observations"}

    native_dates_a, native_values_a = native_window(asset_a, effective_start, effective_end)
    native_dates_b, native_values_b = native_window(asset_b, effective_start, effective_end)
    values_a = asset_values(asset_a)
    values_b = asset_values(asset_b)
    shared_values_a = [float(values_a[index_a[current_date]]) for current_date in selected_shared_dates]
    shared_values_b = [float(values_b[index_b[current_date]]) for current_date in selected_shared_dates]

    metrics_a = asset_metrics(asset_a, native_dates_a, native_values_a, amount_cents, elapsed_days)
    metrics_b = asset_metrics(asset_b, native_dates_b, native_values_b, amount_cents, elapsed_days)
    shared_returns_a = simple_returns(shared_values_a)
    shared_returns_b = simple_returns(shared_values_b)
    correlation = (
        pearson_correlation(shared_returns_a, shared_returns_b)
        if len(shared_returns_a) >= 30 and len(shared_returns_b) >= 30
        else metric_unavailable("insufficient_data")
    )
    amount_usd = amount_cents / 100

    return {
        "status": "ok",
        "scenario": {
            "methodologyVersion": METHODOLOGY_VERSION,
            "methodologyContractHash": METHODOLOGY_HASH,
            "amountCents": amount_cents,
            "requestedStart": requested_start,
            "requestedEnd": requested_end,
            "effectiveStart": effective_start,
            "effectiveEnd": effective_end,
            "startSnap": "exact" if effective_start == requested_start else "forward",
            "endSnap": "exact" if effective_end == requested_end else "backward",
            "elapsedDays": elapsed_days,
            "sharedObservationCount": len(selected_shared_dates),
            "assetA": metrics_a,
            "assetB": metrics_b,
            "pair": {
                "correlation": correlation,
                "sharedReturnCount": len(shared_returns_a),
            },
            "wealthPath": [
                {
                    "date": current_date,
                    "assetAUsd": normalize_zero(amount_usd * float(values_a[index_a[current_date]]) / shared_values_a[0]),
                    "assetBUsd": normalize_zero(amount_usd * float(values_b[index_b[current_date]]) / shared_values_b[0]),
                }
                for current_date in selected_shared_dates
            ],
            "endingValueWinner": compare_ending_value(metrics_a, metrics_b),
            "totalReturnWinner": compare_display_values(metrics_a["totalReturn"], metrics_b["totalReturn"], "displayBasisPoints"),
            "deeperDrawdownAsset": compare_deeper_drawdown(metrics_a, metrics_b),
        },
    }
