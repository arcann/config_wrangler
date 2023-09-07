import logging
from pathlib import Path
from typing import *

from config_wrangler.config_data_loaders.env_config_data_loader import EnvConfigDataLoader
from config_wrangler.config_data_loaders.toml_config_data_loader import TomlConfigDataLoader
from config_wrangler.config_from_loaders import ConfigFromLoaders


class ConfigFromTomlEnv(ConfigFromLoaders):
    # noinspection PyMethodParameters
    def __init__(
            __pydantic_self__,
            file_name: str = 'config.ini',
            start_path: Optional[Union[str, Path]] = None,
            config_load_log_level: int = logging.INFO,
            **kwargs: Dict[str, Any]
    ) -> None:
        env_loader = EnvConfigDataLoader()
        ini_loader = TomlConfigDataLoader(start_path=start_path, file_name=file_name)
        super().__init__(
            _config_data_loaders=[env_loader, ini_loader],
            config_load_log_level=config_load_log_level,
            **kwargs
        )
