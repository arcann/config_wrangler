import logging
import typing

from pydantic import BaseModel, PrivateAttr

from config_wrangler.config_data_loaders.base_config_data_loader import BaseConfigDataLoader
from config_wrangler.config_templates.config_hierarchy import ConfigHierarchy
from config_wrangler.config_templates.credentials import PasswordDefaults
from config_wrangler.utils import merge_configs, interpolate_values


class ConfigFromLoaders(ConfigHierarchy):
    """
    Base class for settings, allowing values to be set by files or environment variables.
    """
    _model_validators: PrivateAttr(default=[])
    passwords: PasswordDefaults = None

    # noinspection PyMethodParameters
    def __init__(
        __pydantic_self__,
        _config_data_loaders: typing.List[BaseConfigDataLoader],
        **kwargs: typing.Dict[str, typing.Any]
    ) -> None:
        """
        Note: Uses something other than `self` the first arg to allow "self" as a settable attribute
        """
        log = logging.getLogger(__name__)

        config_data = dict(**kwargs)
        for loader in _config_data_loaders:
            log.debug(f"Loading config with {loader}")
            loader_config_data = loader.read_config_data(__pydantic_self__)
            merge_configs(config_data, loader_config_data)
        log.debug("Interpolating config macro references")
        interpolate_errors = interpolate_values(config_data, config_data)
        if len(interpolate_errors) > 0:
            log = logging.getLogger(__name__)
            log.error(f"{len(interpolate_errors)} Variable interpolation config errors found:")
            errors_str_list = []
            indent = ' ' * 3
            for error in interpolate_errors:
                error_msg = f"{indent}{error[0]}: {error[1]}"
                log.error(error_msg)
                errors_str_list.append(error_msg)

            errors_str = f"\n".join(errors_str_list)
            raise ValueError(f"Config Interpolation Errors (cnt={len(interpolate_errors)}). Errors=\n{indent}{errors_str}")

        log.debug("Translating config with translate_config_data method")
        config_data = __pydantic_self__.translate_config_data(config_data)
        log.debug(f"Calling pydantic __init__")
        super().__init__(**config_data)
        log.debug("Calling fill_hierarchy to fill in root and parent data")
        __pydantic_self__.validate_model()

    def fill_hierarchy_any_type(
            self,
            value: object,
            parents: typing.List[str],
            errors: set,
    ):
        if isinstance(value, BaseModel):
            self.fill_hierarchy(
                model_level=value,
                parents=parents,
                errors=errors
            )
        elif isinstance(value, list):
            for index, entry in enumerate(value):
                self.fill_hierarchy_any_type(
                    value=entry,
                    parents=parents + [f"[{index}]"],
                    errors=errors
                )
        elif isinstance(value, dict):
            for key, entry in value.items():
                self.fill_hierarchy_any_type(
                    value=entry,
                    parents=parents + [f"[{key}]"],
                    errors=errors
                )

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
            self.fill_hierarchy_any_type(
                value=attr_value,
                parents=parents + [attr_name],
                errors=errors
            )

        # Run any model level validators
        for attr in dir(model_level):
            if attr.startswith('_validate_model_'):
                method = getattr(model_level, attr)
                if callable(method):
                    try:
                        method()
                    except (ValueError, TypeError, AssertionError) as exc:
                        errors.add(repr(exc))

    def validate_model(self):
        errors = set()
        self.fill_hierarchy(
            model_level=self,
            parents=[],
            errors=errors,
        )
        if len(errors) > 0:
            log = logging.getLogger(__name__)
            log.error(f"{len(errors)} config errors found:")
            for error in errors:
                log.error(error)
            indent = ' ' * 3
            errors_str = f"\n{indent}".join(errors)
            raise ValueError(f"Config Errors (cnt={len(errors)}). Errors=\n{indent}{errors_str}")