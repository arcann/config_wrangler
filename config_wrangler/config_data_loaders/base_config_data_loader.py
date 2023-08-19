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

    def read_config_data(self, model: BaseModel) -> MutableMapping:
        return self._init_config_data

    def save_config_data(self, config_data: BaseModel):
        raise RuntimeError(f"{self.__class__.__name__} doesn't deal with files")
