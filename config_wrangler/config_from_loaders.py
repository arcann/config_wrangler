import logging
from typing import *

from config_wrangler.config_data_loaders.base_config_data_loader import BaseConfigDataLoader
from config_wrangler.config_root import ConfigRoot
from config_wrangler.utils import merge_configs, interpolate_values


class ConfigFromLoaders(ConfigRoot):
    """
    Base class for settings, allowing values to be set by files or environment variables.
    """

    # noinspection PyMethodParameters
    def __init__(
        __pydantic_self__,
        _config_data_loaders: List[BaseConfigDataLoader],
        config_load_log_level: int = logging.INFO,
        **kwargs: Dict[str, Any]
    ) -> None:
        """
        Note: Uses something other than `self` the first arg to allow "self" as a settable attribute
        """
        logging.basicConfig(level=config_load_log_level)
        log = logging.getLogger(__name__)

        config_data = dict(**kwargs)
        for loader in _config_data_loaders:
            log.debug(f"Loading config with {loader}")
            loader_config_data = loader.read_config_data(__pydantic_self__)
            merge_configs(config_data, loader_config_data)
        log.debug("Interpolating config macro references")
        interpolate_errors = interpolate_values(config_data, config_data)
        if len(interpolate_errors) > 0:
            log = logging.getLogger(__name__)
            log.error(f"{len(interpolate_errors)} Variable interpolation config errors found:")
            errors_str_list = []
            indent = ' ' * 3
            for error in interpolate_errors:
                error_msg = f"{indent}{error[0]}: {error[1]}"
                log.error(error_msg)
                errors_str_list.append(error_msg)

            errors_str = f"\n".join(errors_str_list)
            raise ValueError(f"Config Interpolation Errors (cnt={len(interpolate_errors)}). Errors=\n{indent}{errors_str}")

        log.debug("Translating config with translate_config_data method")
        config_data = __pydantic_self__.translate_config_data(config_data)
        super().__init__(**config_data)
