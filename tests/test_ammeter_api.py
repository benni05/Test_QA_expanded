import unittest

from src.testing.ammeter_api import AmmeterConfigError, AmmeterError, AmmeterInterface, SocketAmmeter, create_ammeter, create_ammeters
from src.utils.Utils import find_free_port


class ParsingTest(unittest.TestCase):
    """
    Reply parsing, tested directly without any server.
    """

    def test_should_parse_numeric_reply(self):
        """
        Checks a numeric reply, with surrounding whitespace, becomes a float.
        """
        self.assertEqual(AmmeterInterface._parse(" 12.5\n"), 12.5)

    def test_should_raise_given_unusable_reply(self):
        """
        Checks empty, non-numeric and non-finite replies are rejected with a specific message.
        """
        for raw, message in (("", "empty response"), ("hello", "non-numeric"), ("nan", "non-finite"), ("inf", "non-finite")):
            with self.subTest(raw=raw):
                with self.assertRaisesRegex(AmmeterError, message):
                    AmmeterInterface._parse(raw)


class ResultReportingTest(unittest.TestCase):
    """
    A failed measurement is reported, not raised.
    """

    def test_should_report_failure_given_connection_refused(self):
        """
        Checks a port with nothing listening gives a failed result in the unified format.
        """
        result = SocketAmmeter("down", find_free_port(), b"CMD", timeout_seconds=1.0).measure()
        self.assertFalse(result.success)
        self.assertIsNone(result.value)
        self.assertIn("ConnectionRefusedError", result.error)
        self.assertEqual(set(result.to_dict()), {"ammeter", "success", "value", "unit", "timestamp", "duration_seconds", "error"})


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

    def test_should_raise_given_empty_entry(self):
        """
        Checks an empty YAML entry is rejected instead of crashing.
        """
        with self.assertRaisesRegex(AmmeterConfigError, "missing 'port'"):
            create_ammeter("x", None)

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


if __name__ == "__main__":
    unittest.main()
