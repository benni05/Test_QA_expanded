# Ammeter Testing Exercise - Documentation

## Environment

- Python 3.9.6 (macOS system `python3`), run inside a virtual environment at `.venv/`.
- Setup:

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

- Run: `.venv/bin/python main.py`

## Libraries installed

Installed from `requirements.txt`:

| Package | Version |
| --- | --- |
| numpy | 2.0.2 |
| scipy | 1.13.1 |
| matplotlib | 3.9.4 |
| seaborn | 0.13.2 |
| PyYAML | 6.0.3 |
| pandas | 2.3.3 |

`pytz` was also installed automatically as a dependency of `pandas`.

## Bugs found and fixed

### 1. `main.py` returned no data

- **Symptom:** running `main.py` started the servers and exited without printing any measurement.
- **Cause:** the three `request_current_from_ammeter(...)` calls were commented out, and the commands in them were truncated (`b'MEASURE_GREENLEE'`, `b'MEASURE_ENTES'`, `b'MEASURE_CIRCUTOR'`). The server only replies when the received bytes equal its full command exactly. On a mismatch it sends nothing and closes the connection, so the client prints "No data received."
- **Fix:** uncommented the calls and used the full commands:

| Ammeter | Port | Command |
| --- | --- | --- |
| Greenlee | 5001 | `MEASURE_GREENLEE -get_measurement` |
| ENTES | 5002 | `MEASURE_ENTES -get_data` |
| CIRCUTOR | 5003 | `MEASURE_CIRCUTOR -get_measurement` |

- **File:** `main.py`.

### 2. "Address already in use" when restarting

- **Symptom:** running `main.py` a second time shortly after the first raised `OSError: [Errno 48] Address already in use` in all three server threads, followed by `ConnectionRefusedError` in the client.
- **Cause:** the connections from the previous run left the ports in TCP `TIME_WAIT`, and the server sockets did not set `SO_REUSEADDR`, so `bind()` was refused.
- **Fix:** set `SO_REUSEADDR` before `bind()` in `AmmeterEmulatorBase.start_server`. The option is applied only when `sys.platform != "win32"`: on Windows it allows several processes to bind the same live port, and Windows does not block binding to `TIME_WAIT` ports, so it is not needed there.
- **File:** `Ammeters/base_ammeter.py`.
- **Verified:** three consecutive runs each returned a reading from all three ammeters (on macOS; Windows was not tested).

### 3. CIRCUTOR command differed from the README

- **Symptom:** the emulator required `MEASURE_CIRCUTOR -get_measurement -current`, while the README and the commented config give `MEASURE_CIRCUTOR -get_measurement`.
- **Cause:** an undocumented `-current` suffix in the emulator.
- **Fix:** removed the suffix from the emulator so the command matches the README, the config, and Greenlee's `-get_measurement` pattern. The client call in `main.py` was updated to match.
- **Files:** `Ammeters/Circutor_Ammeter.py`, `main.py`.

## Known inconsistencies (not yet addressed)

- The README lists ports 5000, 5001 and 5002; the code uses 5001, 5002 and 5003. The code is internally consistent.
- ENTES uses `-get_data` while the others use `-get_measurement`. This matches the README, so it is treated as intentional; the framework should read each command from configuration instead of assuming a shared one.
- The README mentions `AmmeterTester.py`, `Ammeters/main.py` and `examples/run_test.py`; the actual files are `src/testing/test_framework.py`, `main.py` and `examples/run_tests.py`.
- `src/testing/test_framework.py` is a stub (missing `Dict` import, `run_test` unimplemented) and `src/utils/logger.py` never attaches a handler.
- `config/config.yaml` is empty (NULL values).

## Design decisions

To be added when the testing framework is implemented.
