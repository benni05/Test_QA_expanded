import yaml
from typing import Dict

from .errors import ConfigError

REQUIRED_KEYS = (
    "testing.sampling", "ammeters", "analysis.statistical_metrics", "analysis.visualization.enabled", "analysis.visualization.plot_types",
    "analysis.visualization.output_dir", "analysis.accuracy.confidence_level", "analysis.accuracy.expected_current_a", "result_management.directory",
)


def load_config(config_path: str) -> Dict:
    """
    Loads the YAML config and checks that every required key exists, raising ConfigError with a clear message otherwise.
    """
    # Read and parse the file
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
    except OSError as exc:
        raise ConfigError(f"cannot read config '{config_path}': {exc.strerror or exc}") from exc
    except yaml.YAMLError as exc:
        raise ConfigError(f"config '{config_path}' is not valid YAML: {exc}") from exc

    # Check that every required dotted key is present
    if not isinstance(config, dict):
        raise ConfigError(f"config '{config_path}' must be a YAML mapping")
    missing = [key for key in REQUIRED_KEYS if not _has_key(config, key)]
    if missing:
        raise ConfigError(f"config '{config_path}' is missing: {', '.join(missing)}")

    return config


def _has_key(config: Dict, dotted_key: str) -> bool:
    """
    Returns True if the nested key such as "analysis.accuracy" exists in the config.
    """
    node = config
    for part in dotted_key.split("."):
        if not isinstance(node, dict) or part not in node:
            return False
        node = node[part]

    return True
