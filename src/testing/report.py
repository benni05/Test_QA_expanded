from collections import Counter
from typing import Dict, List, Optional

LABELS = {"mean": "Mean (A)", "median": "Median (A)", "std_dev": "Std dev (A)", "min": "Min (A)", "max": "Max (A)"}
CONSISTENCY_NOTE = "Spread (CV) = std dev / mean: the lower, the steadier the readings. Timing error = how far a sample ran from its scheduled time."
PRECISION_NOTE = "Robust spread = interquartile range / median (not distorted by outliers). The interval is where the true mean lies with the stated confidence; narrower = more precise."


def _fmt(value: Optional[float], spec: str = ".2f", missing: str = "n/a") -> str:
    """
    Returns the value formatted with the spec, or the placeholder when it is None.
    """
    return missing if value is None else format(value, spec)


def _table(headers: List[str], rows: List[List[str]]) -> str:
    """
    Returns the rows as an aligned text table under the headers.
    """
    widths = [max(len(cell) for cell in column) for column in zip(headers, *rows)]
    lines = [headers, ["-" * width for width in widths]] + rows

    return "\n".join("  ".join(cell.ljust(width) for cell, width in zip(line, widths)).rstrip() for line in lines)


def _metric_names(records: List[Dict]) -> List[str]:
    """
    Returns the metric names present in any record, in first-seen order, so one failed ammeter does not hide the columns of the others.
    """
    return list(dict.fromkeys(name for record in records for name in record["analysis"]["metrics"]))


def _find(run: Dict, ammeter: str) -> Optional[Dict]:
    """
    Returns the record of the named ammeter in the run, or None if that run did not include it.
    """
    return next((r for r in run["ammeters"] if r["ammeter"] == ammeter), None)


def _header_lines(run: Dict) -> List[str]:
    """
    Returns the run identity and the sampling settings shared by its ammeters.
    """
    metadata = run["metadata"]
    settings = run["ammeters"][0]["config"]
    lines = ["", f"Run ID: {run['run_id']}", f"Date: {metadata['created_at']}"]
    if metadata["label"]:
        lines.append(f"Label: {metadata['label']}")
    lines.append("")

    # Per-ammeter overrides make the settings differ, so only shared settings are printed
    if any(r["config"] != settings for r in run["ammeters"]):
        return lines + ["Sampling: set per ammeter (see the archived config)", ""]

    # One line per sampling setting that is in use
    for key, text in (("measurements_count", "Sampling measurements: {}"), ("sampling_frequency_hz", "Sampling frequency: {} Hz"), ("total_duration_seconds", "Total duration: {} s")):
        if settings[key]:
            lines.append(text.format(settings[key]))

    return lines + [""]


def _statistics_lines(records: List[Dict]) -> List[str]:
    """
    Returns the statistics table, one column per computed metric.
    """
    names = _metric_names(records)
    rows = []
    for record in records:
        analysis = record["analysis"]
        metrics = [_fmt(analysis["metrics"].get(name), ".4f") for name in names]
        rows.append([record["ammeter"], f"{analysis['valid']}/{analysis['count']}", f"{record['total_seconds']:.2f}"] + metrics)

    return ["STATISTICS", _table(["Ammeter", "Valid samples", "Total duration (s)"] + [LABELS[name] for name in names], rows), ""]


def _consistency_lines(records: List[Dict]) -> List[str]:
    """
    Returns the consistency table: success rate, achieved frequency, spread and timing error.
    """
    rows = []
    for record in records:
        consistency = record["analysis"]["consistency"]
        rows.append([record["ammeter"], f"{consistency['success_rate']:.0%}", _fmt(consistency["actual_frequency_hz"]), _fmt(consistency["coefficient_of_variation"]),
                     f"{consistency['timing_error_ms_mean']:.2f}", f"{consistency['timing_error_ms_max']:.2f}"])
    headers = ["Ammeter", "Success rate", "Actual rate (Hz)", "Spread (CV)", "Timing error mean (ms)", "Timing error max (ms)"]

    return ["CONSISTENCY", _table(headers, rows), CONSISTENCY_NOTE, ""]


def _warning_lines(records: List[Dict]) -> List[str]:
    """
    Returns a warning naming the ammeters that gave no valid sample, with the first error each one reported.
    """
    lines = []
    for record in records:
        if record["analysis"]["valid"] == 0:
            error = next((r["error"] for r in record["results"] if r["error"]), "no samples taken")
            lines.append(f"WARNING: no valid samples from {record['ammeter']} ({error})")

    return lines + [""] if lines else []


def _error_lines(records: List[Dict]) -> List[str]:
    """
    Returns the failed measurements of each ammeter grouped by error message, most frequent first; empty when nothing failed.
    """
    lines = []
    for record in records:
        failures = Counter(r["error"] for r in record["results"] if r["error"])
        if failures:
            lines.append(f"  {record['ammeter']}: {sum(failures.values())} of {record['analysis']['count']} failed")
            lines += [f"    {count}x {error}" for error, count in failures.most_common()]

    return ["ERRORS"] + lines + [""] if lines else []


def _accuracy_lines(accuracy: Dict) -> List[str]:
    """
    Returns the report lines comparing the ammeters: a reliability ranking with precision figures, bias against the expected current, and the verdict.
    """
    level = f"{accuracy['confidence']:.0%}"
    items = accuracy["ammeters"]

    # Precision table in ranking order, best first
    rows = []
    for rank, name in enumerate(accuracy["ranking"], 1):
        item = items[name]
        interval = f"{item['ci_low']:.4f} .. {item['ci_high']:.4f}" if "ci_low" in item else "n/a"
        rows.append([str(rank), name, f"{item['success_rate']:.0%}", _fmt(item.get("cv")), _fmt(item.get("robust_cv")), interval, _fmt(item.get("ci_width_pct"), ".0%")])
    headers = ["Rank", "Ammeter", "Success rate", "Spread (CV)", "Robust spread", f"Mean {level} interval (A)", "Interval width (% of mean)"]
    lines = ["PRECISION (most reliable first)", _table(headers, rows), PRECISION_NOTE, ""]

    # Bias table for the ammeters with an expected current
    rows = [[name, f"{item['expected']:.4f}", f"{item['mean']:.4f}", f"{item['bias_pct']:+.1%}", "yes" if item["expected_in_ci"] else "no"] for name, item in items.items() if "bias_pct" in item]
    if rows:
        lines += ["ACCURACY (against the expected current of the documented model)", _table(["Ammeter", "Expected (A)", "Measured mean (A)", "Bias", f"Expected inside {level} interval"], rows), ""]

    # Verdict
    best = accuracy["most_reliable"]
    lines.append(f"Most reliable: {best} (lowest spread among the ammeters with the highest success rate)" if best else "Most reliable: undetermined (not enough valid samples)")

    return lines


def format_report(run: Dict) -> str:
    """
    Returns a readable summary of an archived run: its identity, statistics, consistency, accuracy comparison and plot files.
    """
    records = run["ammeters"]
    lines = _header_lines(run) + _warning_lines(records) + _statistics_lines(records) + _consistency_lines(records) + _error_lines(records)

    # Accuracy and precision comparison, if the run has one
    if "accuracy" in run:
        lines += [""] + _accuracy_lines(run["accuracy"])

    # Plot files
    plots = [f"  {r['ammeter']}: {', '.join(r['plots'])}" for r in records if r["plots"]]
    if run.get("comparison_plots"):
        plots.append(f"  comparison: {', '.join(run['comparison_plots'])}")
    if plots:
        lines += ["", "PLOTS"] + plots

    return "\n".join(lines)


def format_run_list(summaries: List[Dict]) -> str:
    """
    Returns the archived runs as a table, oldest first.
    """
    if not summaries:
        return "No runs archived yet."

    return _table(["Run ID", "Date", "Label", "Ammeters"], [[s["run_id"], s["created_at"][:19], s["label"], ", ".join(s["ammeters"])] for s in summaries])


def format_comparison(runs: List[Dict]) -> str:
    """
    Returns a table comparing the runs: for each ammeter and metric, the value in every run and the change from the first run to the last.
    """
    rows = []
    for record in runs[0]["ammeters"]:
        name = record["ammeter"]
        found = [_find(run, name) for run in runs]

        # One row per metric, then the spread, each read from every run that has the ammeter
        series = [(LABELS[metric], [f["analysis"]["metrics"].get(metric) if f else None for f in found]) for metric in record["analysis"]["metrics"]]
        series.append(("Spread (CV)", [f["analysis"]["consistency"]["coefficient_of_variation"] if f else None for f in found]))
        for label, values in series:
            first, last = values[0], values[-1]
            change = f"{(last - first) / first:+.1%}" if first and last is not None else "n/a"
            rows.append([name, label] + [_fmt(v, ".4f", "-") for v in values] + [change])

    return _table(["Ammeter", "Metric"] + [run["run_id"] for run in runs] + ["Change"], rows)
