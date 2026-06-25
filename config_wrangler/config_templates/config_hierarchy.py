from __future__ import annotations

import json
import warnings
from pprint import pprint
from typing import MutableMapping, Any, List, Dict, Set, Generator, Tuple, Literal

from config_wrangler.config_wrangler_config import ConfigWranglerConfig
from pydantic import PrivateAttr, BaseModel, ValidationError

private_attrs = ('_root_config', '_parents', '_name_map')


class ConfigHierarchy(BaseModel):
    """
    A non-root member of a hierarchy of configuration items.

    NOTE: This class requires that the top of the hierarchy be an instance of
    :py:class:`config_wrangler.config_root.ConfigRoot`
    """
    model_config = ConfigWranglerConfig(
        validate_default=True,
        validate_assignment=True,
        validate_credentials=True
    )
    _root_config: 'ConfigHierarchy' = PrivateAttr(default=None)
    _DEFAULT_PARENTS = ['parents_not_set']
    _parents: List[str] = PrivateAttr(default=_DEFAULT_PARENTS)
    _name_map: Dict[str, str] = PrivateAttr(default={})
    _private_value_atts: set = PrivateAttr(default_factory=set)

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
        try:
            super().__init__(**data)
        except ValidationError as e:
            # Limit the depth of the traceback
            for error in e.errors():
                try:
                    location = error['ctx']['location']
                    location_str = '.'.join(location)
                    input_data = error['ctx']['input']
                    # Input might not be a dict
                    print(f"input dict for {location_str}:")
                    pprint(input_data, indent=3)
                except Exception:
                    pass
            raise ValidationError.from_exception_data(
                title=e.title,
                line_errors=e.errors(),
            ) from None
        finally:
            pass
        for attr, attr_value in private_holding.items():
            setattr(__pydantic_self__, attr, attr_value)

    def _private_attr_dict(self) -> dict:
        return {
            attr: getattr(self, attr, None) for attr in private_attrs
        }

    def _dict_for_init(
            self,
            exclude: Set[str] | None = None,
    ) -> Dict[str, Any]:
        d = self.model_dump()
        d.update(**self._private_attr_dict())
        if exclude is not None:
            for exclude_attr in exclude:
                if exclude_attr in d:
                    del d[exclude_attr]
        return d

    def full_item_name(self, item_name: str | None = None, delimiter: str = ' -> '):
        """
        The fully qualified name of this config item in the config hierarchy.
        """
        if self._parents == self._DEFAULT_PARENTS:
            parents = [self.__class__.__name__]
        else:
            parents = self._parents

        if item_name is None:
            return delimiter.join(parents)
        else:
            return delimiter.join(parents + [item_name])

    @staticmethod
    def translate_config_data(config_data: MutableMapping):
        """
        Children classes can provide translation logic to allow older config files to be used
        with newer config class definitions.
        """
        return config_data

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

    def set_as_child(self, name: str, other_config_item: 'ConfigHierarchy'):
        warnings.warn(
            'The `set_as_child` method is deprecated; use `add_child` instead.',
            DeprecationWarning,
            stacklevel=2,
        )

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

    def model_dump_non_private(
            self,
            *,
            mode: Literal['json', 'python'] | str = 'python',
            exclude: Set[str] | None = None,
    ) -> dict[str, Any]:

        result = dict()

        if exclude is None:
            exclude = set()

        for key, value in self:
            if key not in exclude:
                if isinstance(value, ConfigHierarchy):
                    result[key] = value.model_dump_non_private(mode=mode, exclude=exclude)
                else:
                    if mode == 'json':
                        result[key] = json.dumps(value)
                    else:
                        result[key] = value
        return result
