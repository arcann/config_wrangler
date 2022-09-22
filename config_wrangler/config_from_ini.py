from typing import *

from config_wrangler.config_from_loaders import ConfigFromLoaders
from config_wrangler.config_data_loaders.ini_config_data_loader import IniConfigDataLoader


class ConfigFromIni(ConfigFromLoaders):
    # noinspection PyMethodParameters
    def __init__(
            __pydantic_self__,
            file_name: str = 'config.ini',
            start_path: Optional[str] = None,
            **kwargs: Dict[str, Any]
    ) -> None:
        """
        Note: Uses something other than `self` the first arg to allow "self" as a settable attribute
        """
        ini_loader = IniConfigDataLoader(start_path=start_path, file_name=file_name)
        super().__init__(
            _config_data_loaders=[ini_loader],
            **kwargs
        )
