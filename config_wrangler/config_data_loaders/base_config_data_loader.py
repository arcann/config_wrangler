import logging
from typing import *

from pydantic import BaseModel


class BaseConfigDataLoader:
    def __init__(self, config_data_dict: Dict[str, Any] = None, **kwargs):
        self.log = logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")
        if config_data_dict is None:
            self._init_config_data = dict(**kwargs)
        else:
            self._init_config_data = dict(**kwargs).update(config_data_dict)

    def _apply_types(self, config_data, model: BaseModel) -> MutableMapping:
        for field in model.__fields__.values():
            self.log.debug(field.alias)
            # if field.is_complex():
            #     raise NotImplementedError
            # else:
            #     config_data[field.alias] =
        return config_data

    def read_config_data(self, model: BaseModel) -> MutableMapping:
        return self._apply_types(self._init_config_data, model)

    def save_config_data(self, config_data: BaseModel):
        raise RuntimeError(f"{self.__class__.__name__} doesn't deal with files")
