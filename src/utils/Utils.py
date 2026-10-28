import random
import socket
import time


def generate_random_float(min_value: float, max_value: float) -> float:
    """
    Returns a random float between min_value and max_value.
    """
    return random.uniform(min_value, max_value)


def sleep_until(deadline: float) -> None:
    """
    Sleeps until time.perf_counter() reaches the deadline, spinning for the last 2 ms because time.sleep alone overshoots.
    """
    while (remaining := deadline - time.perf_counter()) > 0:
        time.sleep(remaining * 0.9 if remaining > 0.002 else 0)


def wait_for_port(port: int, timeout_seconds: float = 10.0, host: str = "localhost") -> bool:
    """
    Waits until something accepts connections on the port and returns True, or returns False after the timeout.
    """
    deadline = time.perf_counter() + timeout_seconds
    while time.perf_counter() < deadline:
        try:
            socket.create_connection((host, port), timeout=0.5).close()
            return True
        except OSError:
            time.sleep(0.1)

    return False
