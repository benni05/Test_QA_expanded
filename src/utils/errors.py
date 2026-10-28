class FrameworkError(ValueError):
    """
    Base class of every error the framework raises on purpose, so entry points can catch them in one place.
    """


class ConfigError(FrameworkError):
    """
    Raised when the config file is missing, unreadable, not valid YAML or lacks a required section or key.
    """


def require_known(names, available, what: str) -> None:
    """
    Raises ConfigError listing the valid names if any of the given names is not in available.
    """
    unknown = [name for name in names if name not in available]
    if unknown:
        raise ConfigError(f"unknown {what} {unknown}, available: {', '.join(available)}")
