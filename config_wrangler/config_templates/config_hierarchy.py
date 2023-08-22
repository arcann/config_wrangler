import collections.abc
from typing import MutableMapping, Any, TYPE_CHECKING, List, Dict, Set, Generator, Tuple, Sequence

from pydantic import PrivateAttr, BaseModel, ValidationError
# noinspection PyProtectedMember
from typing_extensions import deprecated

if TYPE_CHECKING:
    from config_wrangler.config_from_loaders import ConfigFromLoaders


# class SectionMissingError(PydanticValueError):
#     msg_template = 'Section required'
#
#
# class BadValueError(PydanticValueError):
#     msg_template = '{original}. value_provided = {value_str}'
#
#     def __init__(self, original: PydanticValueError, value_str: str) -> None:
#         super().__init__(original=original, value_str=value_str)
#

private_attrs = ('_root_config', '_parents', '_name_map')


class ConfigHierarchy(BaseModel):
    """
    A non-root member of a hierarchy of configuration items.

    NOTE: This class requires that the top of the hierarchy be an instance of
    :py:class:`config_wrangler.config_root.ConfigRoot`
    """
    _root_config: 'ConfigFromLoaders' = PrivateAttr(default=None)
    _parents: List[str] = PrivateAttr(default=['parents_not_set'])
    _name_map: Dict[str, str] = PrivateAttr(default={})
    _private_value_atts = PrivateAttr(default={})

    # noinspection PyMethodParameters
    # noinspection PyProtectedMember
    def __init__(__pydantic_self__, **data: Any) -> None:
        """
        Create a new model by parsing and validating input data from keyword arguments.

        Raises ValidationError if the input data cannot be parsed to form a valid model.

        Uses something other than `self` the first arg to allow "self" as a settable attribute
        """
        private_holding = dict()
        for attr in private_attrs:
            if attr in data:
                private_holding[attr] = data[attr]
                del data[attr]
        super().__init__(**data)
        for attr, attr_value in private_holding.items():
            setattr(__pydantic_self__, attr, attr_value)

    def _private_attr_dict(self) -> dict:
        return {
            attr: getattr(self, attr, None) for attr in private_attrs
        }

    def _dict_for_init(
            self,
            exclude: Set[str] = None,
    ) -> Dict[str, Any]:
        d = self.model_dump()
        d.update(**self._private_attr_dict())
        if exclude is not None:
            for exclude_attr in exclude:
                if exclude_attr in d:
                    del d[exclude_attr]
        return d

    def full_item_name(self, item_name: str = None, delimiter: str = ' -> '):
        """
        The fully qualified name of this config item in the config hierarchy.
        """
        if item_name is None:
            return delimiter.join(self._parents)
        else:
            return delimiter.join(self._parents + [item_name])

    @staticmethod
    def translate_config_data(config_data: MutableMapping):
        """
        Children classes can provide translation logic to allow older config files to be used
        with newer config class definitions.
        """
        return config_data

    def get(self, section, item, fallback=...):
        """
        Used as a drop in replacement for ConfigParser.get() with dynamic config field names
        (using a string variable for the section and item names instead of python code attribute access)

        .. warning::

            With this method Python code checkers (linters) will not warn about invalid config items.
            You can end up with runtime AttributeError errors.
        """
        try:
            section_obj = getattr(self, section)
            return getattr(section_obj, item)
        except AttributeError:
            if fallback is ...:
                raise
            else:
                return fallback

    def getboolean(self, section, item, fallback=...) -> bool:
        """
        Used as a drop in replacement for ConfigParser.getboolean() with dynamic config field names
        (using a string variable for the section and item names instead of python code attribute access)

        .. warning::

            With this method Python code checkers (linters) will not warn about invalid config items.
            You can end up with runtime AttributeError errors.
        """
        value = self.get(section=section, item=item, fallback=fallback)
        if value is None:
            value = False
        if not isinstance(value, bool):
            raise ValueError('getboolean called on non-bool config item')
        return value

    def get_list(self, section, item, fallback=...) -> list:
        """
        Used as a drop in replacement for ConfigParser.get() + list parsing with dynamic config field names
        (using a string variable for the section and item names instead of python code attribute access)
        that is then parsed as a list.

        .. warning::

            With this method Python code checkers (linters) will not warn about invalid config items.
            You can end up with runtime AttributeError errors.
        """
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

    def add_child(self, name: str, child_object: 'ConfigHierarchy'):
        """
        Set this configuration as a child in the hierarchy of another config.
        For any programmatically created config objects this is required so that the
        new object 'knows' where it lives in the hierarchy -- most importantly so that
        it can find the hierarchies root object.
        """
        child_object._parents = self._parents + [name]
        child_object._root_config = self._root_config

    @deprecated(
        'The `set_as_child` method is deprecated; use `add_child` instead.', category=DeprecationWarning
    )
    def set_as_child(self, name: str, other_config_item: 'ConfigHierarchy'):
        self.add_child(name, other_config_item)

    def get_copy(self, copied_by: str = 'get_copy') -> 'ConfigHierarchy':
        """
        Copy this configuration. Useful when you need to programmatically modify a
        configuration without modifying the original base configuration.
        """
        new_instance = self.model_copy(deep=False)
        try:
            self.add_child(copied_by, new_instance)
        except AttributeError:
            # Make the copy its own root
            new_instance._root_config = new_instance
            new_instance._parents = []
        return new_instance

    def __iter__(self) -> Generator[Tuple[str, Any], None, None]:
        """
        Iterate through the values, but hide any password (_private_value_atts)
        values in this output.  Passwords should be directly accessed by attribute name.
        """
        for key, value in super().__iter__():
            if key in self._private_value_atts and value is not None:
                value = '*' * 8
            yield key, value
