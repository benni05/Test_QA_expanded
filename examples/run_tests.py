from src.testing.report import format_report
from src.testing.test_framework import AmmeterTestFramework


def main():
    """
    Tests every configured ammeter against the running emulators and prints the report.
    """
    print(format_report(AmmeterTestFramework().run_all("example")))


if __name__ == "__main__":
    main()
