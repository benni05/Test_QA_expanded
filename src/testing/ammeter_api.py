import math
import socket
import time
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Dict, Optional

DEFAULT_HOST = "localhost"
DEFAULT_TIMEOUT_SECONDS = 2.0
RECV_BUFFER_SIZE = 1024
MAX_RESPONSE_BYTES = 4096
CURRENT_UNIT = "A"


class AmmeterError(Exception):
    """
    Raised when an ammeter replies with something unusable.
    """


class AmmeterConfigError(ValueError):
    """
    Raised when the ammeter configuration is missing or invalid.
    """


@dataclass(frozen=True)
class MeasurementResult:
    """
    Outcome of a single measurement request, identical for every ammeter type and for success and failure alike.
    """

    ammeter: str
    success: bool
    value: Optional[float]
    unit: str
    timestamp: str
    duration_seconds: float
    error: Optional[str]

    def to_dict(self) -> Dict:
        """
        Returns the result as a plain dict, ready for JSON serialization.
        """
        return asdict(self)


class AmmeterInterface(ABC):
    """
    Common contract for every ammeter. Subclasses only provide the raw read; timing, parsing and error reporting are shared.
    """

    def __init__(self, name: str):
        """
        Stores the ammeter name used in results.
        """
        self._name = name

    @property
    def name(self) -> str:
        """
        Returns the ammeter name.
        """
        return self._name

    @abstractmethod
    def _read_raw(self) -> str:
        """
        Requests one measurement and returns the raw text reply. May raise OSError or AmmeterError.
        """
        raise NotImplementedError("Subclasses must implement this method.")

    def measure(self) -> MeasurementResult:
        """
        Takes one measurement. Never raises: failures are reported through the result.
        """
        # Capture the start time for the timestamp and duration
        timestamp = datetime.now(timezone.utc).isoformat()
        start = time.perf_counter()

        # Read and parse the reply, turning any failure into an error message
        value = None
        error = None
        try:
            value = self._parse(self._read_raw())
        except (OSError, ValueError, AmmeterError) as exc:
            error = f"{type(exc).__name__}: {exc}"

        # Build the unified result
        return MeasurementResult(
            ammeter=self._name,
            success=error is None,
            value=value,
            unit=CURRENT_UNIT,
            timestamp=timestamp,
            duration_seconds=time.perf_counter() - start,
            error=error,
        )

    @staticmethod
    def _parse(raw: str) -> float:
        """
        Converts the raw reply to a finite float, raising AmmeterError if it is empty, non-numeric or not finite.
        """
        # Reject empty replies
        text = raw.strip()
        if not text:
            raise AmmeterError("empty response")

        # Reject non-numeric replies
        try:
            value = float(text)
        except ValueError:
            raise AmmeterError(f"non-numeric response: {text[:50]!r}")

        # Reject NaN and infinity
        if not math.isfinite(value):
            raise AmmeterError(f"non-finite response: {text[:50]!r}")

        return value


class SocketAmmeter(AmmeterInterface):
    """
    Ammeter reached over a TCP socket: send a command, read the reply until the server closes the connection.
    """

    def __init__(self, name: str, port: int, command: bytes, host: str = DEFAULT_HOST, timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS):
        """
        Stores the connection settings.
        """
        super().__init__(name)
        self._host = host
        self._port = port
        self._command = command
        self._timeout_seconds = timeout_seconds

    def _read_raw(self) -> str:
        """
        Connects, sends the command and returns the decoded reply.
        """
        chunks = []
        received = 0

        # Connect and send the command
        with socket.create_connection((self._host, self._port), timeout=self._timeout_seconds) as conn:
            conn.sendall(self._command)

            # Read until the server closes the connection, capping the size
            while received < MAX_RESPONSE_BYTES:
                chunk = conn.recv(RECV_BUFFER_SIZE)
                if not chunk:
                    break
                chunks.append(chunk)
                received += len(chunk)

        return b"".join(chunks).decode("utf-8", errors="replace")


def create_ammeter(name: str, settings: Optional[Dict]) -> AmmeterInterface:
    """
    Builds an ammeter from one entry of the "ammeters" config section. Requires port and command.
    """
    # Validate the entry (an empty YAML entry loads as None)
    settings = settings or {}
    for key in ("port", "command"):
        if settings.get(key) is None:
            raise AmmeterConfigError(f"ammeter '{name}': missing '{key}'")

    # Build the socket ammeter, applying defaults for optional keys
    return SocketAmmeter(
        name=name,
        port=int(settings["port"]),
        command=str(settings["command"]).encode("utf-8"),
        host=settings.get("host", DEFAULT_HOST),
        timeout_seconds=float(settings.get("timeout_seconds", DEFAULT_TIMEOUT_SECONDS)),
    )


def create_ammeters(config: Dict) -> Dict[str, AmmeterInterface]:
    """
    Builds every ammeter listed under "ammeters" in the config, keyed by lower-case name.
    """
    # Validate the section
    section = (config or {}).get("ammeters")
    if not section:
        raise AmmeterConfigError("config has no 'ammeters' section")

    return {name.lower(): create_ammeter(name.lower(), settings) for name, settings in section.items()}
