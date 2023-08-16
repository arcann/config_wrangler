from pydantic import ConfigDict


class ConfigWranglerConfig(ConfigDict):
    validate_credentials: bool
    """Should we validate any Credentials on init?"""
