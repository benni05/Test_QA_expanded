import socket
import threading
import unittest

from Ammeters.Circutor_Ammeter import CircutorAmmeter
from Ammeters.Entes_Ammeter import EntesAmmeter
from Ammeters.Greenlee_Ammeter import GreenleeAmmeter
from src.testing.ammeter_api import AmmeterConfigError, SocketAmmeter, create_ammeter, create_ammeters
from src.testing.test_framework import AmmeterTestFramework
from src.utils.Utils import find_free_port, start_in_background


def start_fake_server(reply: bytes = b"", hang: bool = False) -> int:
    """
    Starts a one-shot server that answers with the given bytes (or never answers) and returns its port.
    """
    server = socket.socket()
    server.bind(("localhost", 0))
    server.listen()
    port = server.getsockname()[1]

    def serve():
        """
        Accepts one client, reads its command and replies.
        """
        conn, _ = server.accept()
        with conn, server:
            conn.recv(1024)
            if hang:
                threading.Event().wait(1.0)
            elif reply:
                conn.sendall(reply)

    threading.Thread(target=serve, daemon=True).start()
    return port


class SocketAmmeterTest(unittest.TestCase):
    """
    Result reporting for success and for each failure mode.
    """

    def should_build(self, port: int, timeout: float = 1.0) -> SocketAmmeter:
        """
        Returns a client pointed at the given port.
        """
        return SocketAmmeter("fake", port, b"CMD", timeout_seconds=timeout)

    def test_should_return_value_given_numeric_reply(self):
        """
        Checks a numeric reply becomes a successful result.
        """
        result = self.should_build(start_fake_server(b"12.5")).measure()
        self.assertTrue(result.success)
        self.assertEqual(result.value, 12.5)
        self.assertEqual(result.unit, "A")
        self.assertIsNone(result.error)
        self.assertEqual(result.ammeter, "fake")

    def test_should_report_failure_given_connection_refused(self):
        """
        Checks a closed port gives a failed result instead of raising.
        """
        result = self.should_build(find_free_port()).measure()
        self.assertFalse(result.success)
        self.assertIsNone(result.value)
        self.assertIn("ConnectionRefusedError", result.error)

    def test_should_report_failure_given_timeout(self):
        """
        Checks a server that never answers gives a failed result.
        """
        result = self.should_build(start_fake_server(hang=True), timeout=0.2).measure()
        self.assertFalse(result.success)
        self.assertIn("timeout", result.error.lower())

    def test_should_report_failure_given_empty_reply(self):
        """
        Checks a server that closes without replying gives a failed result.
        """
        result = self.should_build(start_fake_server(b"")).measure()
        self.assertFalse(result.success)
        self.assertIn("empty response", result.error)

    def test_should_report_failure_given_non_numeric_reply(self):
        """
        Checks a garbage reply gives a failed result.
        """
        result = self.should_build(start_fake_server(b"hello")).measure()
        self.assertFalse(result.success)
        self.assertIn("non-numeric", result.error)

    def test_should_report_failure_given_non_finite_reply(self):
        """
        Checks NaN and infinity are rejected.
        """
        for reply in (b"nan", b"inf"):
            result = self.should_build(start_fake_server(reply)).measure()
            self.assertFalse(result.success, reply)
            self.assertIn("non-finite", result.error)

    def test_should_serialize_result_to_dict(self):
        """
        Checks the result exposes all fields as a dict.
        """
        data = self.should_build(start_fake_server(b"1")).measure().to_dict()
        self.assertEqual(set(data), {"ammeter", "success", "value", "unit", "timestamp", "duration_seconds", "error"})


class ConfigTest(unittest.TestCase):
    """
    Building ammeters from configuration.
    """

    def test_should_raise_given_missing_port(self):
        """
        Checks a missing required key is rejected with a clear error.
        """
        with self.assertRaisesRegex(AmmeterConfigError, "missing 'port'"):
            create_ammeter("x", {"command": "C"})

    def test_should_raise_given_missing_command(self):
        """
        Checks a missing command is rejected.
        """
        with self.assertRaisesRegex(AmmeterConfigError, "missing 'command'"):
            create_ammeter("x", {"port": 1})

    def test_should_raise_given_no_ammeters_section(self):
        """
        Checks an empty config is rejected.
        """
        for config in ({}, None, {"ammeters": None}):
            with self.assertRaises(AmmeterConfigError):
                create_ammeters(config)

    def test_should_lowercase_ammeter_names(self):
        """
        Checks names are normalized.
        """
        ammeters = create_ammeters({"ammeters": {"Greenlee": {"port": 1, "command": "C"}}})
        self.assertEqual(list(ammeters), ["greenlee"])


class FrameworkIntegrationTest(unittest.TestCase):
    """
    The framework against the real emulators, using the commands from config.yaml.
    """

    @classmethod
    def setUpClass(cls):
        """
        Starts the three emulators on free ports and points a framework at them.
        """
        cls.framework = AmmeterTestFramework("config/config.yaml")
        emulators = {"greenlee": GreenleeAmmeter, "entes": EntesAmmeter, "circutor": CircutorAmmeter}
        for name, emulator_class in emulators.items():
            port = find_free_port()
            start_in_background(emulator_class(port), port)
            cls.framework.ammeters[name]._port = port

    def test_should_measure_every_ammeter_type(self):
        """
        Checks each configured type returns a successful, positive reading through the same interface.
        """
        for name in ("greenlee", "entes", "circutor"):
            result = self.framework.measure(name)
            self.assertTrue(result.success, f"{name}: {result.error}")
            self.assertGreater(result.value, 0)

    def test_should_measure_all_given_no_arguments(self):
        """
        Checks measure_all returns one result per ammeter.
        """
        results = self.framework.measure_all()
        self.assertEqual(sorted(r.ammeter for r in results), ["circutor", "entes", "greenlee"])

    def test_should_accept_any_letter_case(self):
        """
        Checks the type name is case-insensitive.
        """
        self.assertTrue(self.framework.measure("ENTES").success)

    def test_should_raise_given_unknown_type(self):
        """
        Checks an unknown type lists the valid ones.
        """
        with self.assertRaisesRegex(ValueError, "available: circutor, entes, greenlee"):
            self.framework.measure("nope")


if __name__ == "__main__":
    unittest.main()
