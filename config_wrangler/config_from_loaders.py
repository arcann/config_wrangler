import logging
import typing

from pydantic import BaseModel, PrivateAttr

from config_data_loaders.base_config_data_loader import BaseConfigDataLoader
from config_templates.config_hierarchy import ConfigHierarchy
from config_templates.credentials import PasswordDefaults, Credentials
from utils import merge_configs, interpolate_values


class ConfigFromLoaders(ConfigHierarchy):
    """
    Base class for settings, allowing values to be set by files or environment variables.
    """
    passwords: PasswordDefaults = None

    _name_map = PrivateAttr(default={})

    # noinspection PyMethodParameters
    def __init__(
        __pydantic_self__,
        _config_data_loaders: typing.List[BaseConfigDataLoader],
        **kwargs: typing.Dict[str, typing.Any]
    ) -> None:
        log = logging.getLogger(__name__)
        # Uses something other than `self` the first arg to allow "self" as a settable attribute
        config_data = dict(**kwargs)
        for loader in _config_data_loaders:
            log.debug(f"Loading config with {loader}")
            loader_config_data = loader.read_config_data(__pydantic_self__)
            merge_configs(config_data, loader_config_data)
        log.debug("Interpolating config macro references")
        interpolate_values(config_data, config_data)
        log.debug("Translating config with translate_config_data method")
        config_data = __pydantic_self__.translate_config_data(config_data)
        log.debug(f"Calling pydantic __init__")
        super().__init__(**config_data)
        log.debug("Calling fill_hierarchy to fill in root and parent data")
        errors = set()
        __pydantic_self__.fill_hierarchy(
            model_level=__pydantic_self__,
            parents=[],
            errors=errors,
        )
        if len(errors) > 0:
            log.error(f"{len(errors)} config errors found:")
            for error in errors:
                log.error(error)
            indent = ' '*3
            errors_str = f"\n{indent}".join(errors)
            raise ValueError(f"Config Errors (cnt={len(errors)}). Errors=\n{indent}{errors_str}")

    def fill_hierarchy(
            self,
            model_level: BaseModel,
            parents: typing.List[str],
            errors: set,
    ):
        log = logging.getLogger(__name__)
        if len(parents) > 10:
            raise ValueError(f"Possible model self reference {parents}")
        try:
            model_level._root_config = self
            model_level._parents = parents
            # noinspection PyUnresolvedReferences
            name = model_level.full_item_name()
            log.debug(f"fill_hierarchy on {name}")
        except AttributeError as e:
            log.warning(f"{parents} {repr(model_level)} is not an instance inheriting from ConfigHierarchy: {e}")
        for attr_name, attr_value in model_level.__dict__.items():
            if isinstance(attr_value, BaseModel):
                self.fill_hierarchy(
                    model_level=attr_value,
                    parents=parents + [attr_name],
                    errors=errors
                )

            if isinstance(attr_value, Credentials):
                if attr_value.validate_password_on_load:
                    try:
                        _ = attr_value.get_password()
                    except Exception as e:
                        log.error(f"Error: {repr(e)}")
                        errors.add(repr(e))

    # noinspection PyMethodMayBeStatic
    def translate_config_data(self, config_data: typing.MutableMapping):
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
