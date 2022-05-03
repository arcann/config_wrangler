import typing

from config_wrangler.config_data_loaders.env_config_data_loader import EnvConfigDataLoader
from config_wrangler.config_data_loaders.ini_config_data_loader import IniConfigDataLoader
from config_wrangler.config_from_loaders import ConfigFromLoaders


class ConfigFromIniEnv(ConfigFromLoaders):
    # noinspection PyMethodParameters
    def __init__(
            __pydantic_self__,
            file_name: str = 'config.ini',
            start_path: typing.Optional[str] = None,
            **kwargs: typing.Dict[str, typing.Any]
    ) -> None:
        env_loader = EnvConfigDataLoader()
        ini_loader = IniConfigDataLoader(start_path=start_path, file_name=file_name)
        super().__init__(
            _config_data_loaders=[env_loader, ini_loader],
            **kwargs
        )
