import inspect
import logging
import warnings
from typing import List, Any

from pydantic import PrivateAttr, BaseModel

from config_wrangler.config_templates.config_hierarchy import ConfigHierarchy
from config_wrangler.config_templates.credentials import PasswordDefaults
from config_wrangler.config_wrangler_config import ConfigWranglerConfig

private_attrs = ('_root_config', '_parents', '_name_map')


class ConfigRoot(ConfigHierarchy):
    """
    The root member of a hierarchy of configuration items.

    NOTE: Children config items should be instances of
    :py:class:`config_wrangler.config_templates.config_hierarchy.ConfigHierarchy`
    """
    model_config = ConfigWranglerConfig(
        validate_default=True,
        validate_assignment=True,
        validate_credentials=True
    )

    _fill_done: bool = PrivateAttr(default=False)
    # _model_validators: PrivateAttr(default=[])

    passwords: PasswordDefaults = PasswordDefaults()
    """
    Default configuration for passwords within this config hierarchy.
    """

    # noinspection PyMethodParameters
    def __init__(__pydantic_self__, **data: Any) -> None:
        log = logging.getLogger(__name__)
        log.debug(f"Calling pydantic __init__")
        super().__init__(**data)
        log.debug("Calling validate_model / fill_hierarchy to fill in root and parent data")
        __pydantic_self__.validate_model()

    def fill_hierarchy_any_type(
            self,
            value: object,
            parents: List[str],
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
            parents: List[str],
            errors: set,
    ):
        self._fill_done = True
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

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            try:
                method_list = inspect.getmembers(model_level, predicate=inspect.ismethod)
            except Exception:
                method_list = []
        for validation_method_name, validation_method in method_list:
            qualified_name = f"{model_level.__class__.__qualname__}.{validation_method_name}"
            if hasattr(validation_method, '_is_config_hierarchy_validator'):
                try:
                    validation_method()
                except (ValueError, TypeError, AssertionError) as exc:
                    log.exception(exc)
                    errors.add(f"Failed check {parents}  {qualified_name} with {repr(exc)}")
            elif validation_method_name.startswith('_validate_model_'):
                warnings.warn(
                    f"{qualified_name}"
                    " uses deprecated name based validation function finding. "
                    "Please use @config_hierarchy_validator instead."
                )
                try:
                    validation_method()
                except (ValueError, TypeError, AssertionError) as exc:
                    log.exception(exc)
                    errors.add(f"Failed check {parents}  {qualified_name} with {repr(exc)}")

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
