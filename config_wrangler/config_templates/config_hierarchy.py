from typing import MutableMapping, Any, TYPE_CHECKING, List, Dict

from pydantic import PrivateAttr, BaseModel

if TYPE_CHECKING:
    from config_wrangler.config_from_loaders import ConfigFromLoaders


class ConfigHierarchy(BaseModel):
    """
    NOTE: This class requires that the top of the hierarchy be an instance of ConfigFromLoaders
    """
    _root_config: 'ConfigFromLoaders' = PrivateAttr(default=None)
    _parents: List[str] = PrivateAttr()
    _name_map: Dict[str, str] = PrivateAttr(default={})

    # noinspection PyMethodParameters
    def __init__(__pydantic_self__, **data: Any) -> None:
        """
        Create a new model by parsing and validating input data from keyword arguments.

        Raises ValidationError if the input data cannot be parsed to form a valid model.

        Uses something other than `self` the first arg to allow "self" as a settable attribute
        """
        super().__init__(**data)

    def full_item_name(self, item_name: str = None, delimiter: str = ' -> '):
        try:
            if item_name is None:
                return delimiter.join(self._parents)
            else:
                return delimiter.join(self._parents + [item_name])
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

    def getboolean(self, section, item, fallback=...) -> bool:
        value = self.get(section=section, item=item, fallback=fallback)
        if value is None:
            value = False
        if not isinstance(value, bool):
            raise ValueError('getboolean called on non-bool config item')
        return value

    def get_list(self, section, item, fallback=...) -> list:
        value = self.get(section=section, item=item, fallback=fallback)
        if value is None:
            value = []
        if not isinstance(value, list):
            raise ValueError('get_list called on non-list config item')
        return value

    def __getitem__(self, section):
        try:
            section_obj = getattr(self, section)
            return section_obj.dict()
        except AttributeError as e:
            raise KeyError(str(e))
