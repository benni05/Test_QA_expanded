from typing import Dict, List

from .ammeter_api import AmmeterInterface, MeasurementResult, create_ammeters
from ..utils.config import load_config


class AmmeterTestFramework:
    """
    Entry point of the framework: loads the config and gives one interface to every configured ammeter.
    """

    def __init__(self, config_path: str = "config/config.yaml"):
        """
        Loads the config and builds the ammeters it describes.
        """
        self.config = load_config(config_path)
        self.ammeters: Dict[str, AmmeterInterface] = create_ammeters(self.config)

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

    def run_test(self, ammeter_type: str) -> Dict:
        """
        Runs a sampling test. Not implemented yet: sampling is the next step.
        """
        raise NotImplementedError("Sampling is not implemented yet.")
