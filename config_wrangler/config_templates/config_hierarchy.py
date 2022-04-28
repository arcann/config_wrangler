from typing import MutableMapping

from pydantic import PrivateAttr, BaseModel, typing


class ConfigHierarchy(BaseModel):
    _root_config = PrivateAttr()
    _parents = PrivateAttr()
    _name_map = PrivateAttr(default={})

    def full_item_name(self, item_name: str = None, delimiter: str = ' -> '):
        try:
            if item_name is None:
                return delimiter.join(self._parents)
            else:
                return delimiter.join(self._parents + item_name)
        except AttributeError as e:
            raise AttributeError(f"{e} not found in {repr(self)}")

    @staticmethod
    def translate_config_data(config_data: MutableMapping):
        return config_data

    def _translate_name(self, old_name):
        if old_name in self._name_map:
            return self._name_map[old_name]
        else:
            return old_name

    def get(self, section, item, fallback=...):
        try:
            section_obj = getattr(self, self._translate_name(section))
            return getattr(section_obj, item)
        except AttributeError:
            if fallback is ...:
                raise
            else:
                return fallback

    def __getitem__(self, section):
        try:
            section_obj = getattr(self, section)
            return section_obj.dict()
        except AttributeError as e:
            raise KeyError(str(e))
