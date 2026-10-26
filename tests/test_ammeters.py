import threading
import unittest

from Ammeters.Circutor_Ammeter import CircutorAmmeter
from Ammeters.Entes_Ammeter import EntesAmmeter
from Ammeters.Greenlee_Ammeter import GreenleeAmmeter
from src.testing.ammeter_api import SocketAmmeter, create_ammeters
from src.testing.test_framework import AmmeterTestFramework
from src.utils.Utils import find_free_port, start_in_background

EMULATORS = {"greenlee": GreenleeAmmeter, "entes": EntesAmmeter, "circutor": CircutorAmmeter}

# Output range implied by the input ranges documented in the README
EXPECTED_RANGES = {
    "greenlee": (1.0 / 100.0, 10.0 / 0.1),
    "entes": (0.01 * 500, 0.1 * 2000),
    "circutor": (10 * 0.1 * 0.001, 10 * 1.0 * 0.01),
}
SAMPLES = 100


class AmmeterEmulatorTest(unittest.TestCase):
    """
    Validates the real ammeter emulators through the framework, using the commands from config.yaml.
    """

    @classmethod
    def setUpClass(cls):
        """
        Starts the three emulators on free ports and points the framework at them.
        """
        cls.framework = AmmeterTestFramework("config/config.yaml")
        cls.ports = {}
        for name, emulator_class in EMULATORS.items():
            cls.ports[name] = find_free_port()
            cls.framework.config["ammeters"][name]["port"] = cls.ports[name]
            start_in_background(emulator_class(cls.ports[name]), cls.ports[name])
        cls.framework.ammeters = create_ammeters(cls.framework.config)

    def readings(self, name: str, count: int = SAMPLES):
        """
        Returns the values of count consecutive measurements, failing if any of them failed.
        """
        results = [self.framework.measure(name) for _ in range(count)]
        for result in results:
            self.assertTrue(result.success, f"{name}: {result.error}")

        return [result.value for result in results]

    def test_should_return_reading_within_documented_range(self):
        """
        Checks every reading lies inside the range implied by the documented measurement logic.
        """
        for name, (low, high) in EXPECTED_RANGES.items():
            with self.subTest(ammeter=name):
                for value in self.readings(name):
                    self.assertTrue(low <= value <= high, f"{value} outside [{low}, {high}]")

    def test_should_return_varying_readings(self):
        """
        Checks consecutive readings are not constant.
        """
        for name in EMULATORS:
            with self.subTest(ammeter=name):
                self.assertGreater(len(set(self.readings(name, 20))), 1)

    def test_should_return_mean_near_expected_value(self):
        """
        Checks the sample mean is close to the analytical mean of the documented distribution (ENTES and CIRCUTOR).
        """
        expected = {"entes": 0.055 * 1250, "circutor": 10 * 0.55 * 0.0055}
        for name, mean in expected.items():
            with self.subTest(ammeter=name):
                values = self.readings(name, 500)
                self.assertAlmostEqual(sum(values) / len(values), mean, delta=mean * 0.15)

    def test_should_reject_command_of_another_ammeter(self):
        """
        Checks an ammeter does not answer a command meant for a different ammeter.
        """
        for name in EMULATORS:
            other = next(n for n in EMULATORS if n != name)
            with self.subTest(ammeter=name, command_of=other):
                wrong = SocketAmmeter(name, self.ports[name], self.framework.config["ammeters"][other]["command"].encode())
                result = wrong.measure()
                self.assertFalse(result.success)
                self.assertIn("empty response", result.error)

    def test_should_keep_serving_after_invalid_command(self):
        """
        Checks a bad request does not break the server for the next valid one.
        """
        for name in EMULATORS:
            with self.subTest(ammeter=name):
                self.assertFalse(SocketAmmeter(name, self.ports[name], b"GARBAGE").measure().success)
                self.assertTrue(self.framework.measure(name).success)

    def test_should_serve_concurrent_clients(self):
        """
        Checks simultaneous clients all get a valid reading.
        """
        for name in EMULATORS:
            with self.subTest(ammeter=name):
                results = []
                threads = [threading.Thread(target=lambda: results.append(self.framework.measure(name))) for _ in range(10)]
                for thread in threads:
                    thread.start()
                for thread in threads:
                    thread.join()
                self.assertEqual(len(results), 10)
                self.assertTrue(all(r.success for r in results))

    def test_should_measure_all_given_no_arguments(self):
        """
        Checks measure_all returns one successful result per ammeter.
        """
        results = self.framework.measure_all()
        self.assertEqual(sorted(r.ammeter for r in results), sorted(EMULATORS))
        self.assertTrue(all(r.success for r in results))

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
