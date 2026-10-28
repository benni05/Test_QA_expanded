import os
import statistics
from typing import Callable, Dict, List

from .sampler import SamplingResult
from ..utils.errors import require_known


def _time_series(ax, times: List[float], values: List[float]) -> None:
    """
    Draws each reading against the time it was taken.
    """
    ax.plot(times, values, marker="o", markersize=3)
    ax.set_xlabel("time (s)")
    ax.set_ylabel("current (A)")


def _histogram(ax, times: List[float], values: List[float]) -> None:
    """
    Draws how often each current range occurred.
    """
    ax.hist(values, bins=min(20, max(5, len(values) // 5)))
    ax.set_xlabel("current (A)")
    ax.set_ylabel("samples")


def _rolling_stats(ax, times: List[float], values: List[float]) -> None:
    """
    Draws the readings with their rolling mean and a band of one rolling standard deviation, which shows drift and changing noise.
    """
    window = max(3, len(values) // 5)
    spans = [values[max(0, i - window + 1):i + 1] for i in range(len(values))]
    means = [statistics.mean(span) for span in spans]
    stds = [statistics.stdev(span) if len(span) > 1 else 0.0 for span in spans]

    ax.plot(times, values, marker="o", markersize=3, alpha=0.4, label="reading")
    ax.plot(times, means, label=f"rolling mean ({window})")
    ax.fill_between(times, [m - s for m, s in zip(means, stds)], [m + s for m, s in zip(means, stds)], alpha=0.2, label="+/- 1 std dev")
    ax.set_xlabel("time (s)")
    ax.set_ylabel("current (A)")
    ax.legend()


def _normalized_boxplot(ax, records: List[Dict], accuracy: Dict) -> None:
    """
    Draws every ammeter's readings divided by its own mean, so ammeters with very different currents can be compared on one scale.
    """
    names = [r["ammeter"] for r in records if accuracy["ammeters"][r["ammeter"]].get("mean")]
    data = [[x["value"] / accuracy["ammeters"][r["ammeter"]]["mean"] for x in r["results"] if x["success"]] for r in records if r["ammeter"] in names]
    ax.boxplot(data)
    ax.set_xticklabels(names)
    ax.axhline(1, color="gray", linewidth=0.8)
    ax.set_ylabel("reading / mean")


def _bias(ax, records: List[Dict], accuracy: Dict) -> None:
    """
    Draws each ammeter's bias against its expected current, with the confidence interval of the mean as the error bar; a bar crossing zero is within noise.
    """
    items = {name: a for name, a in accuracy["ammeters"].items() if "bias_pct" in a}
    errors = [[(a["mean"] - a["ci_low"]) / a["expected"] * 100 for a in items.values()], [(a["ci_high"] - a["mean"]) / a["expected"] * 100 for a in items.values()]]
    ax.bar(list(items), [a["bias_pct"] * 100 for a in items.values()], yerr=errors, capsize=6)
    ax.axhline(0, color="gray", linewidth=0.8)
    ax.set_ylabel(f"bias vs expected (%), {accuracy['confidence']:.0%} interval")


PLOTS = {"time_series": _time_series, "histogram": _histogram, "rolling_stats": _rolling_stats}
COMPARISON_PLOTS = {"normalized_boxplot": _normalized_boxplot, "bias": _bias}


def _render(names: List[str], draw: Callable, title: Callable[[str], str], file_name: Callable[[str], str], output_dir: str) -> List[str]:
    """
    Saves one PNG per plot name, calling draw(name, ax) to fill each figure, and returns the file paths.
    """
    # Draw headless so it works without a display (imported here so matplotlib loads only when plotting)
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    # Draw and save each plot
    os.makedirs(output_dir, exist_ok=True)
    paths = []
    for name in names:
        fig, ax = plt.subplots()
        draw(name, ax)
        ax.set_title(title(name))
        paths.append(os.path.join(output_dir, file_name(name)))
        fig.savefig(paths[-1], dpi=100, bbox_inches="tight")
        plt.close(fig)

    return paths


def plot_measurements(run: SamplingResult, plot_types: List[str], output_dir: str) -> List[str]:
    """
    Saves one PNG per requested plot type for the successful readings of one ammeter and returns the file paths.
    """
    require_known(plot_types, PLOTS, "plot types")

    # Keep only successful readings with the time they were taken
    points = [(offset, r.value) for offset, r in zip(run.offsets_seconds, run.results) if r.success]
    if not points:
        return []
    times, values = (list(column) for column in zip(*points))

    return _render(plot_types, lambda name, ax: PLOTS[name](ax, times, values), lambda name: f"{run.ammeter} - {name}", lambda name: f"{run.ammeter}_{name}.png", output_dir)


def plot_comparison(records: List[Dict], accuracy: Dict, plot_types: List[str], output_dir: str) -> List[str]:
    """
    Saves one PNG per requested plot type that compares the ammeters of a run with each other and returns the file paths.
    """
    require_known(plot_types, COMPARISON_PLOTS, "comparison plot types")
    if not plot_types or not any("mean" in a for a in accuracy["ammeters"].values()):
        return []

    return _render(plot_types, lambda name, ax: COMPARISON_PLOTS[name](ax, records, accuracy), lambda name: f"ammeter comparison - {name}", lambda name: f"comparison_{name}.png", output_dir)
