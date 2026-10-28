# Ammeter Testing Framework

Tests three ammeter emulators (Greenlee, ENTES, CIRCUTOR): samples each one, analyzes and plots the readings, compares the ammeters' precision and accuracy, and archives every run.

## Setup and usage

```sh
python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
.venv/bin/python main.py [label]                      # start the emulators, test every ammeter, archive and print the report
.venv/bin/python history.py list                      # archived runs
.venv/bin/python history.py show latest               # reprint a run (or give a run id)
.venv/bin/python history.py compare <id> <id> ...     # compare runs side by side
.venv/bin/python -m pytest tests                      # unit tests (no emulators needed)
```

Everything is configured in `config/config.yaml`: ammeter ports and commands, sampling (set two of count, duration, frequency), statistics, plots, expected currents and the archive directory.
Per ammeter entry: `enabled: false` skips it, `sampling:` overrides the shared sampling, `error_rate: 0.2` (and optionally `error_seed`) simulates failed reads.
Plots: `plot_types` (per ammeter: time_series, histogram, rolling_stats) and `comparison_plots` (across ammeters: normalized_boxplot, bias).

## Project structure

- `Ammeters/`: the emulators (`base_ammeter.py` plus one class per type) and a simple client.
- `src/testing/`: `ammeter_api.py` (unified measurement API, fault injection), `sampler.py`, `analyzer.py`, `visualizer.py`, `accuracy.py`, `result_store.py`, `report.py`, `test_framework.py` (entry point).
- `src/utils/`: `config.py` (loading and validation), `errors.py` (shared error types), `Utils.py` (helpers).
- `tests/`: unit tests. `examples/run_tests.py`: minimal usage example. `DOCUMENTATION.md`: design decisions and findings.

## Emulators

| Ammeter | Port | Command | Method |
| --- | --- | --- | --- |
| Greenlee | 5001 | `MEASURE_GREENLEE -get_measurement` | Ohm's law, I = V / R (V 1-10 V, R 0.1-100 ohm) |
| ENTES | 5002 | `MEASURE_ENTES -get_data` | Hall effect, I = B * K (B 0.01-0.1 T, K 500-2000) |
| CIRCUTOR | 5003 | `MEASURE_CIRCUTOR -get_measurement` | Rogowski coil, I = integral of V dt (V 0.1-1 V, dt 0.001-0.01 s) |
