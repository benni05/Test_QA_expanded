import time
from dataclasses import dataclass
from typing import List, Optional

from .ammeter_api import AmmeterInterface, MeasurementResult
from ..utils.Utils import sleep_until
from ..utils.errors import FrameworkError


class SamplingConfigError(FrameworkError):
    """
    Raised when the sampling settings are missing, non-positive or insufficient.
    """


@dataclass(frozen=True)
class SamplingConfig:
    """
    Sampling settings. Set at least two of the three; the third follows from them. If all three are set, sampling stops at whichever limit is hit first.
    """

    measurements_count: Optional[int] = None
    total_duration_seconds: Optional[float] = None
    sampling_frequency_hz: Optional[float] = None

    def __post_init__(self):
        """
        Rejects non-positive values and fewer than two settings.
        """
        values = (self.measurements_count, self.total_duration_seconds, self.sampling_frequency_hz)
        if any(v is not None and v <= 0 for v in values):
            raise SamplingConfigError("sampling values must be positive")
        if sum(v is not None for v in values) < 2:
            raise SamplingConfigError("set at least two of measurements_count, total_duration_seconds, sampling_frequency_hz")

    @property
    def interval_seconds(self) -> float:
        """
        Returns the time between two samples.
        """
        if self.sampling_frequency_hz is not None:
            return 1.0 / self.sampling_frequency_hz

        return self.total_duration_seconds / self.measurements_count

    def includes(self, index: int) -> bool:
        """
        Returns True if the sample with this zero-based index is within the count and duration limits.
        """
        within_count = self.measurements_count is None or index < self.measurements_count
        within_duration = self.total_duration_seconds is None or index * self.interval_seconds < self.total_duration_seconds

        return within_count and within_duration


@dataclass(frozen=True)
class SamplingResult:
    """
    All samples of one run, with the actual time of each one so timing accuracy can be checked.
    """

    ammeter: str
    config: SamplingConfig
    results: List[MeasurementResult]
    offsets_seconds: List[float]
    total_seconds: float


def sample(ammeter: AmmeterInterface, config: SamplingConfig) -> SamplingResult:
    """
    Takes measurements on a fixed schedule. Each sample is timed from the run start, not from the previous sample, so delays do not accumulate.
    A slow measurement makes the next samples fire late until the schedule is caught up.
    """
    results, offsets = [], []
    interval = config.interval_seconds
    start = time.perf_counter()

    # Wait for each scheduled tick, then measure and record when it actually ran
    index = 0
    while config.includes(index):
        sleep_until(start + index * interval)
        offsets.append(time.perf_counter() - start)
        results.append(ammeter.measure())
        index += 1

    return SamplingResult(ammeter.name, config, results, offsets, time.perf_counter() - start)
