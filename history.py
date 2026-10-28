import argparse
import sys

from src.testing.report import format_comparison, format_report, format_run_list
from src.testing.result_store import ResultStore
from src.utils.config import load_config
from src.utils.errors import FrameworkError


def main() -> int:
    """
    Lists, shows and compares archived test runs. Run ids can be replaced by "latest".
    """
    parser = argparse.ArgumentParser(description="Browse archived ammeter test runs.")

    # Define the commands
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list", help="list all archived runs")
    commands.add_parser("show", help="show one run").add_argument("run_id")
    commands.add_parser("compare", help="compare two or more runs").add_argument("run_ids", nargs="+")
    args = parser.parse_args()

    # Run the chosen command, reporting errors cleanly
    try:
        store = ResultStore(load_config("config/config.yaml")["result_management"]["directory"])
        if args.command == "list":
            print(format_run_list(store.list_runs()))
        elif args.command == "show":
            print(format_report(store.load(args.run_id)))
        else:
            if len(args.run_ids) < 2:
                parser.error("compare needs at least two run ids")
            print(format_comparison([store.load(run_id) for run_id in args.run_ids]))
    except FrameworkError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
