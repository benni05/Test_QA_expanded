from Ammeters.Circutor_Ammeter import CircutorAmmeter
from Ammeters.Entes_Ammeter import EntesAmmeter
from Ammeters.Greenlee_Ammeter import GreenleeAmmeter
from src.testing.test_framework import AmmeterTestFramework
from src.utils.Utils import start_in_background

EMULATORS = {"greenlee": GreenleeAmmeter, "entes": EntesAmmeter, "circutor": CircutorAmmeter}

if __name__ == "__main__":
    framework = AmmeterTestFramework()

    # Start each emulator on the port configured in config.yaml
    for name, emulator_class in EMULATORS.items():
        port = framework.config["ammeters"][name]["port"]
        start_in_background(emulator_class(port), port)

    # Request one measurement from every ammeter
    for result in framework.measure_all():
        print(f"{result.ammeter}: {result.value} {result.unit}" if result.success else f"{result.ammeter}: FAILED - {result.error}")
