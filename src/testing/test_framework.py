import os
import platform
from datetime import datetime, timezone
from typing import Dict, List, Optional

from .accuracy import assess
from .ammeter_api import AmmeterInterface, MeasurementResult, create_ammeters
from .analyzer import METRICS, build_record
from .result_store import ResultStore, new_run_id
from .sampler import SamplingConfig, SamplingConfigError, sample
from .visualizer import PLOTS, plot_measurements
from ..utils.config import load_config
from ..utils.errors import require_known


class AmmeterTestFramework:
    """
    Entry point of the framework: loads the config and gives one interface to every configured ammeter.
    """

    def __init__(self, config_path: str = "config/config.yaml"):
        """
        Loads the config, validates the settings and builds the ammeters it describes, so a bad config fails before any sampling starts.
        """
        self.config = load_config(config_path)
        analysis = self.config["analysis"]

        # Validate the settings that would otherwise fail late
        require_known(analysis["statistical_metrics"], METRICS, "metrics")
        require_known(analysis["visualization"]["plot_types"], PLOTS, "plot types")
        try:
            self.sampling = SamplingConfig(**self.config["testing"]["sampling"])
        except TypeError as exc:
            raise SamplingConfigError(f"invalid testing.sampling settings: {exc}") from exc
        self.ammeters: Dict[str, AmmeterInterface] = create_ammeters(self.config)
        self.store = ResultStore(self.config["result_management"]["directory"])

    def get_ammeter(self, ammeter_type: str) -> AmmeterInterface:
        """
        Returns the ammeter for the given type, raising ValueError with the valid names if it is unknown.
        """
        ammeter = self.ammeters.get(ammeter_type.lower())
        if ammeter is None:
            raise ValueError(f"unknown ammeter '{ammeter_type}', available: {', '.join(sorted(self.ammeters))}")

        return ammeter

    def measure(self, ammeter_type: str) -> MeasurementResult:
        """
        Takes one measurement from the given ammeter type.
        """
        return self.get_ammeter(ammeter_type).measure()

    def measure_all(self) -> List[MeasurementResult]:
        """
        Takes one measurement from every configured ammeter.
        """
        return [ammeter.measure() for ammeter in self.ammeters.values()]

    def run_test(self, ammeter_type: str, sampling: Optional[SamplingConfig] = None, output_dir: Optional[str] = None) -> Dict:
        """
        Samples the given ammeter, analyzes the readings and returns the run as a plain dict with "analysis" and "plots" added.
        Uses testing.sampling and analysis from the config unless a SamplingConfig is passed; plots go to output_dir or the configured one.
        """
        analysis = self.config["analysis"]
        visualization = analysis["visualization"]

        # Sample and analyze
        run = sample(self.get_ammeter(ammeter_type), sampling or self.sampling)
        record = build_record(run, analysis["statistical_metrics"])

        # Plot if enabled
        record["plots"] = plot_measurements(run, visualization["plot_types"], output_dir or visualization["output_dir"]) if visualization["enabled"] else []

        return record

    def run_all(self, label: str = "") -> Dict:
        """
        Tests every ammeter as one run: gives it a unique id, attaches metadata (time, label, environment, full config), archives it and returns it.
        Plots go to a folder named after the run id, so earlier runs keep theirs.
        """
        run_id = new_run_id()
        plots_dir = os.path.join(self.config["analysis"]["visualization"]["output_dir"], run_id)

        # Test every ammeter and collect the records
        run = {
            "run_id": run_id,
            "metadata": {
                "created_at": datetime.now(timezone.utc).isoformat(),
                "label": label,
                "python_version": platform.python_version(),
                "platform": platform.platform(),
                "config": self.config,
            },
            "ammeters": [self.run_test(name, output_dir=plots_dir) for name in self.ammeters],
        }

        # Compare the ammeters with each other
        accuracy = self.config["analysis"]["accuracy"]
        run["accuracy"] = assess(run["ammeters"], accuracy["expected_current_a"], accuracy["confidence_level"])

        # Archive the run
        self.store.save(run)

        return run
