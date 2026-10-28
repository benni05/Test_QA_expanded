import math
import tempfile
import unittest
from unittest import mock

from src.testing.accuracy import assess
from src.testing.ammeter_api import AmmeterConfigError, AmmeterInterface, FaultInjectingAmmeter, create_ammeters
from src.testing.analyzer import analyze, build_record
from src.testing.report import format_comparison, format_report
from src.testing.result_store import ResultStore, ResultStoreError, new_run_id
from src.testing.visualizer import plot_comparison, plot_measurements
from src.testing.sampler import SamplingConfig, SamplingConfigError, sample
from src.utils.tdist import t_cdf, t_ppf

# (degrees of freedom, probability, t value) computed with scipy
T_REFERENCES = [
    (1, 0.975, 12.706204736432095),
    (2, 0.975, 4.302652729696142),
    (19, 0.975, 2.093024054408263),
    (10, 0.995, 3.16927267261695),
    (1000, 0.975, 1.9623390808264074),
    (4, 0.9, 1.5332062740589432),
]
from src.testing.test_framework import AmmeterTestFramework
from src.utils.config import ConfigError, load_config
from src.utils.errors import FrameworkError


class FakeAmmeter(AmmeterInterface):
    """
    Ammeter that replays canned replies, so no emulator or socket is needed.
    """

    def __init__(self, name, replies):
        """
        Stores the replies, repeating the last one when they run out.
        """
        super().__init__(name)
        self._replies = list(replies)

    def _read_raw(self) -> str:
        """
        Returns the next canned reply, raising it if it is an exception.
        """
        reply = self._replies.pop(0) if len(self._replies) > 1 else self._replies[0]
        if isinstance(reply, Exception):
            raise reply

        return reply


def fast_config(count):
    """
    Returns a sampling config that takes the given number of samples at 1 kHz.
    """
    return SamplingConfig(measurements_count=count, sampling_frequency_hz=1000)


def run_of(name, replies, count=None):
    """
    Samples a fake ammeter fast and returns the analyzed record.
    """
    return build_record(sample(FakeAmmeter(name, replies), fast_config(count or len(replies))))


def archived_run(*records):
    """
    Wraps records in the shape of a full run, as run_all builds it.
    """
    records = [{**record, "plots": []} for record in records]

    return {"run_id": new_run_id(), "metadata": {"created_at": "2026-01-01T00:00:00+00:00", "label": ""}, "ammeters": records, "accuracy": assess(records, {})}


class MeasureTest(unittest.TestCase):
    """
    Measurement results and error handling.
    """

    def test_should_return_value_given_valid_reply(self):
        """
        A numeric reply becomes a successful result.
        """
        result = FakeAmmeter("a", ["1.5\n"]).measure()
        self.assertTrue(result.success)
        self.assertEqual(result.value, 1.5)

    def test_should_report_failure_given_bad_reply(self):
        """
        Empty, non-numeric, non-finite replies and socket errors never raise.
        """
        for reply in ["", "abc", "nan", "inf", ConnectionRefusedError("down"), TimeoutError("slow")]:
            result = FakeAmmeter("a", [reply]).measure()
            self.assertFalse(result.success, reply)
            self.assertIsNone(result.value)
            self.assertTrue(result.error)


class ConfigTest(unittest.TestCase):
    """
    Config loading and validation.
    """

    def test_should_raise_given_missing_file(self):
        """
        A missing config file gives ConfigError.
        """
        with self.assertRaises(ConfigError):
            load_config("does-not-exist.yaml")

    def test_should_raise_given_missing_sections(self):
        """
        A config without the required sections gives ConfigError naming them.
        """
        with mock.patch("builtins.open", mock.mock_open(read_data="testing: {}")):
            with self.assertRaisesRegex(ConfigError, "ammeters"):
                load_config("x.yaml")

    def test_should_raise_given_ammeter_without_port(self):
        """
        An ammeter entry needs port and command.
        """
        with self.assertRaises(AmmeterConfigError):
            create_ammeters({"ammeters": {"a": {"command": "X"}}})
        with self.assertRaises(AmmeterConfigError):
            create_ammeters({})


class SamplingTest(unittest.TestCase):
    """
    Sampling settings and schedule.
    """

    def test_should_raise_given_invalid_settings(self):
        """
        Fewer than two settings, or non-positive values, are rejected.
        """
        with self.assertRaises(SamplingConfigError):
            SamplingConfig(measurements_count=5)
        with self.assertRaises(SamplingConfigError):
            SamplingConfig(measurements_count=0, sampling_frequency_hz=10)

    def test_should_take_requested_count(self):
        """
        The run has the configured number of samples.
        """
        self.assertEqual(len(run_of("a", ["1"], count=7)["results"]), 7)

    def test_should_derive_third_setting(self):
        """
        Duration and count give the interval.
        """
        self.assertAlmostEqual(SamplingConfig(measurements_count=10, total_duration_seconds=5).interval_seconds, 0.5)


class AnalysisTest(unittest.TestCase):
    """
    Statistics and accuracy assessment.
    """

    def test_should_compute_statistics(self):
        """
        Mean, median and min/max over successful readings only.
        """
        analysis = run_of("a", ["1", "2", "3", "x"])["analysis"]
        self.assertEqual(analysis["valid"], 3)
        self.assertEqual(analysis["metrics"]["mean"], 2)
        self.assertEqual(analysis["metrics"]["max"], 3)

    def test_should_handle_all_failed(self):
        """
        A run with no valid readings still analyzes and assesses without raising.
        """
        record = run_of("a", [ConnectionRefusedError("down")], count=3)
        self.assertEqual(record["analysis"]["metrics"], {})
        self.assertIsNone(assess([record], {"a": 1.0})["most_reliable"])

    def test_should_reject_unknown_metric(self):
        """
        An unknown metric name raises ValueError.
        """
        with self.assertRaises(ValueError):
            analyze(sample(FakeAmmeter("a", ["1"]), fast_config(2)), ["bogus"])

    def test_should_pick_steadiest_ammeter(self):
        """
        The ammeter with the lower spread is most reliable, and bias is measured against the expected value.
        """
        steady = run_of("steady", ["10", "10.1", "9.9", "10", "10.05"])
        noisy = run_of("noisy", ["1", "20", "5", "30", "2"])
        result = assess([noisy, steady], {"steady": 10.0})
        self.assertEqual(result["most_reliable"], "steady")
        self.assertEqual(result["ranking"], ["steady", "noisy"])
        self.assertAlmostEqual(result["ammeters"]["steady"]["bias_pct"], 0.0, places=2)
        self.assertTrue(result["ammeters"]["steady"]["expected_in_ci"])
        self.assertTrue(math.isfinite(result["ammeters"]["noisy"]["ci_width_pct"]))


class TDistributionTest(unittest.TestCase):
    """
    Student's t quantiles used for the confidence interval.
    """

    def test_should_match_reference_quantiles(self):
        """
        Quantiles agree with reference values (computed with scipy) to 8 digits.
        """
        for df, probability, expected in T_REFERENCES:
            self.assertAlmostEqual(t_ppf(probability, df), expected, places=8)

    def test_should_be_symmetric_and_invert_the_cdf(self):
        """
        The median is 0, the lower tail mirrors the upper one, and t_cdf undoes t_ppf.
        """
        self.assertEqual(t_ppf(0.5, 7), 0.0)
        self.assertAlmostEqual(t_ppf(0.025, 19), -t_ppf(0.975, 19), places=10)
        self.assertAlmostEqual(t_cdf(t_ppf(0.9, 6), 6), 0.9, places=10)

    def test_should_reject_invalid_input(self):
        """
        A probability outside (0, 1) or a non-positive df raises.
        """
        with self.assertRaises(ValueError):
            t_ppf(1.0, 5)
        with self.assertRaises(ValueError):
            t_ppf(0.9, 0)


class ResultStoreTest(unittest.TestCase):
    """
    Archiving and retrieval.
    """

    def test_should_save_load_and_reject_bad_ids(self):
        """
        A saved run loads back, duplicates and unsafe or unknown ids are rejected.
        """
        with tempfile.TemporaryDirectory() as directory:
            store = ResultStore(directory)
            run = {"run_id": new_run_id(), "metadata": {}, "ammeters": []}
            store.save(run)
            self.assertEqual(store.load("latest")["run_id"], run["run_id"])
            with self.assertRaises(ResultStoreError):
                store.save(run)
            with self.assertRaises(ResultStoreError):
                store.load("../x")
            with self.assertRaises(ResultStoreError):
                store.load("20200101T000000Z-00000000")


class ReportTest(unittest.TestCase):
    """
    Report formatting.
    """

    def test_should_keep_metric_columns_given_first_ammeter_failed(self):
        """
        A fully failed first ammeter does not remove the metric columns of the others, and a warning names it.
        """
        run = archived_run(run_of("dead", [ConnectionRefusedError("down")], count=3), run_of("ok", ["1", "2", "3"]))
        report = format_report(run)
        self.assertIn("Mean (A)", report)
        self.assertIn("WARNING: no valid samples from dead", report)
        self.assertIn("Most reliable: ok", report)

    def test_should_list_errors_by_kind(self):
        """
        Failed measurements are listed per ammeter with a count for each error message.
        """
        report = format_report(archived_run(run_of("flaky", ["1", ConnectionResetError("reset"), ConnectionResetError("reset"), "2"])))
        self.assertIn("flaky: 2 of 4 failed", report)
        self.assertIn("2x ConnectionResetError: reset", report)

    def test_should_compare_runs(self):
        """
        The comparison lists each metric of every run and the change between the first and the last.
        """
        first, second = archived_run(run_of("a", ["1", "1"])), archived_run(run_of("a", ["2", "2"]))
        self.assertIn("+100.0%", format_comparison([first, second]))


class FaultInjectionTest(unittest.TestCase):
    """
    Error simulation.
    """

    def test_should_fail_every_read_given_rate_one(self):
        """
        With rate 1 every measurement fails and is reported, never raised.
        """
        ammeter = FaultInjectingAmmeter(FakeAmmeter("a", ["1"]), 1.0, seed=1)
        self.assertFalse(any(ammeter.measure().success for _ in range(20)))

    def test_should_pass_every_read_given_rate_zero(self):
        """
        With rate 0 the wrapped ammeter is untouched.
        """
        ammeter = FaultInjectingAmmeter(FakeAmmeter("a", ["1"]), 0.0)
        self.assertTrue(all(ammeter.measure().success for _ in range(20)))

    def test_should_reject_invalid_rate_and_wrap_from_config(self):
        """
        A rate outside 0..1 is a config error, and error_rate in the config wraps the ammeter.
        """
        with self.assertRaises(AmmeterConfigError):
            FaultInjectingAmmeter(FakeAmmeter("a", ["1"]), 1.5)
        ammeters = create_ammeters({"ammeters": {"a": {"port": 1, "command": "X", "error_rate": 0.5}}})
        self.assertIsInstance(ammeters["a"], FaultInjectingAmmeter)


class FrameworkValidationTest(unittest.TestCase):
    """
    Bad settings fail on construction, before any sampling.
    """

    def test_should_fail_early_given_unknown_metric_or_plot(self):
        """
        Unknown metrics, plot types and sampling keys raise a FrameworkError from the constructor.
        """
        config = load_config("config/config.yaml")
        for path, value in (("analysis.statistical_metrics", ["bogus"]), ("analysis.visualization.plot_types", ["bogus"]), ("testing.sampling", {"bogus": 1})):
            broken = {**config, "analysis": {**config["analysis"], "visualization": dict(config["analysis"]["visualization"])}, "testing": dict(config["testing"])}
            section, *keys = path.split(".")
            target = broken[section]
            for key in keys[:-1]:
                target = target[key]
            target[keys[-1]] = value
            with mock.patch("src.testing.test_framework.load_config", return_value=broken):
                with self.assertRaises(FrameworkError, msg=path):
                    AmmeterTestFramework()


class ConfigDrivenTest(unittest.TestCase):
    """
    Per-ammeter settings and the advanced plots.
    """

    def test_should_apply_per_ammeter_settings(self):
        """
        An ammeter can be disabled or given its own sampling settings.
        """
        config = load_config("config/config.yaml")
        config["ammeters"]["entes"]["enabled"] = False
        config["ammeters"]["circutor"]["sampling"] = {"measurements_count": 4, "sampling_frequency_hz": 100}
        with mock.patch("src.testing.test_framework.load_config", return_value=config):
            framework = AmmeterTestFramework()
        self.assertEqual(sorted(framework.ammeters), ["circutor", "greenlee"])
        self.assertEqual(framework.sampling_overrides["circutor"].measurements_count, 4)
        self.assertNotIn("greenlee", framework.sampling_overrides)

    def test_should_draw_every_plot_type(self):
        """
        Per-ammeter and comparison plots are written as PNG files.
        """
        records = [run_of("a", ["1", "2", "3", "2", "1", "2"]), run_of("b", ["10", "11", "9", "10", "10", "12"])]
        accuracy = assess(records, {"a": 2.0})
        with tempfile.TemporaryDirectory() as directory:
            run = sample(FakeAmmeter("a", ["1", "2", "3", "2", "1", "2"]), fast_config(6))
            self.assertEqual(len(plot_measurements(run, ["time_series", "histogram", "rolling_stats"], directory)), 3)
            self.assertEqual(len(plot_comparison(records, accuracy, ["normalized_boxplot", "bias"], directory)), 2)
            self.assertEqual(plot_comparison(records, accuracy, [], directory), [])


if __name__ == "__main__":
    unittest.main()
