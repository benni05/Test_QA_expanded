import statistics
from dataclasses import asdict
from typing import Dict, List, Optional

from .sampler import SamplingResult
from ..utils.errors import require_known

METRICS = {
    "mean": statistics.mean,
    "median": statistics.median,
    "std_dev": lambda values: statistics.stdev(values) if len(values) > 1 else 0.0,
    "min": min,
    "max": max,
}


def analyze(run: SamplingResult, metrics: Optional[List[str]] = None) -> Dict:
    """
    Computes the requested statistics over the successful readings (all METRICS if none are named), plus consistency figures:
    success rate, coefficient of variation (std_dev / mean), the sampling frequency actually achieved and how far the samples drifted from their schedule.
    """
    # Validate the requested metric names
    names = metrics or list(METRICS)
    require_known(names, METRICS, "metrics")

    # Statistics over the successful readings only
    values = [r.value for r in run.results if r.success]
    mean = statistics.mean(values) if values else None
    cv = METRICS["std_dev"](values) / mean if mean else None

    # Timing error of each sample against its scheduled time
    interval = run.config.interval_seconds
    timing_ms = [abs(offset - index * interval) * 1000 for index, offset in enumerate(run.offsets_seconds)]

    return {
        "count": len(run.results),
        "valid": len(values),
        "failed": len(run.results) - len(values),
        "metrics": {name: METRICS[name](values) for name in names} if values else {},
        "consistency": {
            "success_rate": len(values) / len(run.results),
            "coefficient_of_variation": cv,
            "actual_frequency_hz": (len(run.offsets_seconds) - 1) / run.offsets_seconds[-1] if len(run.offsets_seconds) > 1 else None,
            "timing_error_ms_mean": statistics.mean(timing_ms),
            "timing_error_ms_max": max(timing_ms),
        },
    }


def build_record(run: SamplingResult, metrics: Optional[List[str]] = None) -> Dict:
    """
    Returns the sampling run as a plain dict with its "analysis" added, ready for plotting, reporting and archiving.
    """
    return {**asdict(run), "analysis": analyze(run, metrics)}
