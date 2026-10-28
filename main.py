import contextlib
import io
import sys
import threading

from Ammeters.Circutor_Ammeter import CircutorAmmeter
from Ammeters.Entes_Ammeter import EntesAmmeter
from Ammeters.Greenlee_Ammeter import GreenleeAmmeter
from src.testing.report import format_report
from src.testing.test_framework import AmmeterTestFramework
from src.utils.Utils import wait_for_port
from src.utils.config import load_config
from src.utils.errors import FrameworkError

CONFIG_PATH = "config/config.yaml"
EMULATORS = {"greenlee": GreenleeAmmeter, "entes": EntesAmmeter, "circutor": CircutorAmmeter}


def start_emulators(config: dict) -> None:
    """
    Starts an emulator thread for every configured ammeter that has one, on the port from the config, and waits until each accepts connections.
    """
    ports = {}
    for name, settings in config["ammeters"].items():
        emulator = EMULATORS.get(name.lower())
        if emulator and settings.get("port"):
            ports[name] = settings["port"]
            threading.Thread(target=emulator(settings["port"]).start_server, daemon=True).start()

    # Wait for the servers instead of sleeping a fixed time
    for name, port in ports.items():
        if not wait_for_port(port):
            raise FrameworkError(f"emulator '{name}' did not start on port {port}")


def main() -> int:
    """
    Starts the emulators, runs the full test, archives it and prints the report. Returns 1 on a configuration or archive error, or if an ammeter gave no valid sample.
    """
    # Hide the emulators' own debug prints so only the report is shown
    with contextlib.redirect_stdout(io.StringIO()):
        try:
            start_emulators(load_config(CONFIG_PATH))

            # Test every ammeter, archive the run and label it with the command-line text, if any
            run = AmmeterTestFramework(CONFIG_PATH).run_all(" ".join(sys.argv[1:]))
        except FrameworkError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1

    print(format_report(run))
    print(f"\nArchived. Review later with: python history.py show {run['run_id']}")

    return 0 if all(record["analysis"]["valid"] for record in run["ammeters"]) else 1


if __name__ == "__main__":
    sys.exit(main())
