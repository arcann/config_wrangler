from typing import MutableMapping, Any, TYPE_CHECKING, List, Dict

from pydantic import PrivateAttr, BaseModel, MissingError, PydanticValueError, ValidationError

if TYPE_CHECKING:
    from config_wrangler.config_from_loaders import ConfigFromLoaders


class SectionMissingError(PydanticValueError):
    msg_template = 'Section required'


class BadValueError(PydanticValueError):
    msg_template = '{original}. value_provided = {value_str}'

    def __init__(self, original: PydanticValueError, value_str: str) -> None:
        super().__init__(original=original, value_str=value_str)


class ConfigHierarchy(BaseModel):
    """
    NOTE: This class requires that the top of the hierarchy be an instance of ConfigFromLoaders
    """
    _root_config: 'ConfigFromLoaders' = PrivateAttr(default=None)
    _parents: List[str] = PrivateAttr()
    _name_map: Dict[str, str] = PrivateAttr(default={})

    # noinspection PyMethodParameters
    # noinspection PyProtectedMember
    def __init__(__pydantic_self__, **data: Any) -> None:
        """
        Create a new model by parsing and validating input data from keyword arguments.

        Raises ValidationError if the input data cannot be parsed to form a valid model.

        Uses something other than `self` the first arg to allow "self" as a settable attribute
        """
        try:
            super().__init__(**data)
        except ValidationError as e:
            # Change missing sections errors to show that and not missing field
            for err_wrapper in e.raw_errors:
                original_exc = err_wrapper.exc
                if isinstance(original_exc, MissingError):
                    field_name = err_wrapper._loc
                    field = e.model.__fields__[field_name]
                    if hasattr(field.type_, '__fields__'):
                        err_wrapper.exc = SectionMissingError(
                            exc=err_wrapper.exc,
                            _loc=err_wrapper._loc,
                        )
                else:
                    if isinstance(original_exc, ValidationError):
                        pass
                    elif not isinstance(original_exc, BadValueError):
                        # Change the exception to one that shows the value, if we can get it
                        try:
                            value_limit = 30
                            value = str(data[err_wrapper._loc])
                            if len(value) <= value_limit:
                                value_str = value
                            else:
                                value_str = f"{value[:value_limit]}...value truncated"
                            value_str = value_str.replace('\n', '\\n')

                            err_wrapper.exc = BadValueError(
                                original=original_exc,
                                value_str=value_str
                            )
                        except KeyError:
                            pass
            raise e

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

    def set_as_child(self, name: str, otherConfigItem: 'ConfigHierarchy'):
        otherConfigItem._parents = self._parents + [name]
        otherConfigItem._root_config = self._root_config
