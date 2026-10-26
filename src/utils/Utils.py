import random
import socket
import threading
import time

def generate_random_float(min_value: float, max_value: float) -> float:
    """Generate a random float between min_value and max_value."""
    return random.uniform(min_value, max_value)


def find_free_port() -> int:
    """
    Returns a TCP port that is free right now.
    """
    with socket.socket() as s:
        s.bind(("localhost", 0))
        return s.getsockname()[1]


def wait_for_port(port: int, timeout_seconds: float = 5.0) -> None:
    """
    Blocks until something accepts connections on the port, raising TimeoutError otherwise.
    """
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            socket.create_connection(("localhost", port), timeout=0.2).close()
            return
        except OSError:
            time.sleep(0.05)

    raise TimeoutError(f"port {port} did not open within {timeout_seconds}s")


def start_in_background(server, port: int) -> None:
    """
    Runs server.start_server() in a daemon thread and waits until its port is open.
    """
    threading.Thread(target=server.start_server, daemon=True).start()
    wait_for_port(port)
