import math
import statistics
from typing import Dict, List, Optional

from scipy import stats


def _assess_ammeter(record: Dict, expected: Optional[float], confidence: float) -> Dict:
    """
    Returns precision figures (spread, robust spread, confidence interval of the mean) and, if an expected value is given, the bias against it.
    """
    values = [r["value"] for r in record["results"] if r["success"]]
    n = len(values)
    result = {"valid": n, "success_rate": record["analysis"]["consistency"]["success_rate"], "expected": expected}
    if n < 2:
        return result

    # Spread relative to the mean (CV) and the outlier-resistant version based on the interquartile range
    mean = statistics.mean(values)
    std = statistics.stdev(values)
    q1, _, q3 = statistics.quantiles(values, n=4)
    median = statistics.median(values)

    # Confidence interval of the mean from the t distribution (valid for small samples)
    margin = float(stats.t.ppf((1 + confidence) / 2, n - 1)) * std / math.sqrt(n)
    result.update({
        "mean": mean,
        "cv": std / mean if mean else None,
        "robust_cv": (q3 - q1) / median if median else None,
        "ci_low": mean - margin,
        "ci_high": mean + margin,
        "ci_width_pct": 2 * margin / mean if mean else None,
    })

    # Bias against the expected value, and whether that value lies inside the interval
    if expected:
        result.update({"bias_pct": (mean - expected) / expected, "expected_in_ci": result["ci_low"] <= expected <= result["ci_high"]})

    return result


def assess(records: List[Dict], expected: Dict[str, float], confidence: float = 0.95) -> Dict:
    """
    Compares the ammeters of one run. Ranks them by reliability (highest success rate first, then lowest coefficient of variation)
    and quantifies each one's precision and, where an expected current is configured, its bias against it.
    """
    # Precision and bias per ammeter
    ammeters = {r["ammeter"]: _assess_ammeter(r, (expected or {}).get(r["ammeter"]), confidence) for r in records}

    # Rank by success rate, then by spread (ammeters without a spread go last)
    ranking = sorted(ammeters, key=lambda name: (-ammeters[name]["success_rate"], _spread(ammeters[name])))
    most_reliable = ranking[0] if ranking and ammeters[ranking[0]].get("cv") is not None else None

    return {"confidence": confidence, "ammeters": ammeters, "ranking": ranking, "most_reliable": most_reliable}


def _spread(assessment: Dict) -> float:
    """
    Returns the ammeter's coefficient of variation, or infinity when it has none so it ranks last.
    """
    return math.inf if assessment.get("cv") is None else assessment["cv"]
