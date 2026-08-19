import logging
from typing import *

from config_wrangler.config_data_loaders.base_config_data_loader import BaseConfigDataLoader
from config_wrangler.config_root import ConfigRoot


class ConfigFromLoaders(ConfigRoot):
    """
    Base class for settings, allowing values to be set by files or environment variables.
    """

    # noinspection PyMethodParameters
    def __init__(
        __pydantic_self__,
        _config_data_loaders: List[BaseConfigDataLoader] | None = None,
        config_load_log_level: int = logging.INFO,
        **kwargs: Dict[str, Any]
    ) -> None:
        if _config_data_loaders is not None:
            config_data = __pydantic_self__._get_config_data_from_loaders(
                config_data_loaders=_config_data_loaders,
                config_load_log_level=config_load_log_level,
                starting_config_data=kwargs,
            )
        else:
            config_data = kwargs
        # Pass to pydantic
        super().__init__(**config_data)




