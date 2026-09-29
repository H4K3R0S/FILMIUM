from dataclasses import dataclass

# ==========          CORE CONFIG          ==========

@dataclass(frozen=True)
class CoreConfig:
    """
    Minimal configuration model for CORE.

    This configuration is intentionally small for version 0.1.
    More advanced loading from files and environment variables will be added later.
    """

    app_name: str = "CORE AI Operating System"
    app_version: str = "0.1.0"
    active_domain: str = "filmium"
    debug: bool = True


def load_core_config() -> CoreConfig:
    """
    Load the CORE configuration.

    For version 0.1 this returns default values.
    Later this function will load from config files and environment variables.

    Returns:
        CoreConfig instance.
    """
    return CoreConfig()


core_config = load_core_config()