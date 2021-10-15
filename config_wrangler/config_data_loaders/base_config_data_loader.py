import logging
import os
import typing
from copy import deepcopy

from pydantic import BaseModel

from config_wrangler.config_exception import ConfigError


class BaseConfigDataLoader:
    def __init__(self, config_data_dict: typing.Dict[str, typing.Any] = None, **kwargs):
        self.log = logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")
        if config_data_dict is None:
            self._init_config_data = dict(**kwargs)
        else:
            self._init_config_data = dict(**kwargs).update(config_data_dict)

    def _apply_types(self, config_data, model: BaseModel) -> typing.MutableMapping:
        for field in model.__fields__.values():
            self.log.debug(field.alias)
            # if field.is_complex():
            #     raise NotImplementedError
            # else:
            #     config_data[field.alias] =
        return config_data

    def read_config_data(self, model: BaseModel) -> typing.MutableMapping:
        return self._apply_types(self._init_config_data)

    def save_config_data(self, config_data: BaseModel):
        raise RuntimeError(f"{self.__class__.__name__} doesn't deal with files")


class EnvConfigDataLoader(BaseConfigDataLoader):
    """
    Copied initial version from Pydantic BaseSettings.
    Made to fit into ConfigLoader approach with nested models.
    """

    def __init__(self, env_prefix: str = None, config_data_dict: typing.Dict[str, typing.Any] = None, **kwargs):
        super().__init__(config_data_dict=config_data_dict, **kwargs)
        self.env_prefix = env_prefix or ''

    def read_config_data(self, model: BaseModel) -> typing.MutableMapping:
        config_data = deepcopy(self._init_config_data)

        env_vars = {k.lower(): v for k, v in os.environ.items()}

        for field in model.__fields__.values():
            env_val: typing.Optional[str] = None
            # Note: field.field_info.extra['env_names'] is set from the 'env' variable on the field or in Config.
            #       See https://pydantic-docs.helpmanual.io/usage/settings/#environment-variable-names
            if 'env_names' in field.field_info.extra:
                for env_name in field.field_info.extra['env_names']:
                    env_name = self.env_prefix + env_name
                    env_val = env_vars.get(env_name.lower())
                    if env_val is not None:
                        break
            if env_val is None:
                for env_name in [field.alias, field.name]:
                    env_name = self.env_prefix + env_name
                    env_val = env_vars.get(env_name.lower())
                    if env_val is not None:
                        break

            if field.is_complex():
                if env_val is not None:
                    try:
                        env_val = config_data.__config__.json_loads(env_val)  # type: ignore
                    except ValueError as e:
                        raise ConfigError(f'error parsing JSON for "{field}"') from e
                else:
                    pass
                    # TODO: Look for nested env var variables by concatenating field names with underscores
                    # DATABASE_HOST
                    # DATABASE_PORT
                    # MY_CONNECTION_HOST_NAME
                    # MY_CONNECTION_PORT

            # Only set the value if it is not already in our config_data
            if env_val is not None and field.alias not in config_data:
                config_data[field.alias] = env_val
        return config_data


