import logging
from typing import List, Any

from pydantic import PrivateAttr, BaseModel, PydanticValueError

from config_wrangler.config_templates.config_hierarchy import ConfigHierarchy
from config_wrangler.config_templates.credentials import PasswordDefaults


class BadValueError(PydanticValueError):
    msg_template = '{original}. value_provided = {value_str}'

    def __init__(self, original: PydanticValueError, value_str: str) -> None:
        super().__init__(original=original, value_str=value_str)


private_attrs = ('_root_config', '_parents', '_name_map')


class ConfigRoot(ConfigHierarchy):
    """
    The root member of a hierarchy of configuration items.

    NOTE: Children config items should be instances of
    :py:class:`config_wrangler.config_templates.config_hierarchy.ConfigHierarchy`
    """
    class Config:
        validate_all = True
        validate_assignment = True
        allow_mutation = True
        validate_credentials = True

    _fill_done: bool = PrivateAttr(default=False)
    # _model_validators: PrivateAttr(default=[])
    passwords: PasswordDefaults = None
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
