import os
from typing import List

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


PLOTS = {"time_series": _time_series, "histogram": _histogram}


def plot_measurements(run: SamplingResult, plot_types: List[str], output_dir: str) -> List[str]:
    """
    Saves one PNG per requested plot type for the successful readings and returns the file paths.
    """
    # Validate the requested plot types
    require_known(plot_types, PLOTS, "plot types")

    # Keep only successful readings with the time they were taken
    points = [(offset, r.value) for offset, r in zip(run.offsets_seconds, run.results) if r.success]
    if not points:
        return []
    times, values = zip(*points)

    # Draw headless so it works without a display (imported here so matplotlib loads only when plotting)
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    # Draw and save each plot
    os.makedirs(output_dir, exist_ok=True)
    paths = []
    for name in plot_types:
        fig, ax = plt.subplots()
        PLOTS[name](ax, list(times), list(values))
        ax.set_title(f"{run.ammeter} - {name}")
        paths.append(os.path.join(output_dir, f"{run.ammeter}_{name}.png"))
        fig.savefig(paths[-1], dpi=100, bbox_inches="tight")
        plt.close(fig)

    return paths
