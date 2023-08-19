from typing import TypeVar, Generic, List

from pydantic import field_validator

from config_wrangler.config_templates.config_hierarchy import ConfigHierarchy

RefConfigHierarchy = TypeVar('RefConfigHierarchy', bound=ConfigHierarchy)


class DynamicallyReferenced(ConfigHierarchy):
    """
    Represents a reference to a statically defined section of the config.
    The data type of the section can be any subclass of ConfigHierarchy.
    The validator will check that the reference exists.
    """
    # TODO: validator will check that the reference exists.
    ref: str

    @field_validator('ref')
    @classmethod
    def _validate_phase_1(cls, value):
        if value == '':
            raise ValueError('Blank is not valid for a DynamicallyReferenced section')
        return value

    # TODO: Change to _config_hierarchy_validators decorator
    def _validate_model_reference(self):
        _ = self.get_referenced()

    def get_referenced(self) -> ConfigHierarchy:
        if self.ref is None:
            raise ValueError(f"DynamicallyReferenced {self} is not set")
        elif self._root_config is None:
            raise RuntimeError(
                "DynamicallyReferenced._root_config is none. "
                " Either the root class is not ConfigFromLoaders or "
                "ConfigFromLoaders.fill_hierarchy did not work."
            )
        else:
            parts = self.ref.split('.')

            model = self._root_config
            for part in parts:
                try:
                    model = getattr(model, part)
                except AttributeError:
                    raise ValueError(f"Referenced section {self.ref} not found in model.")
            return model

    def __str__(self):
        return f"{self.ref}"

    def __repr__(self):
        return f"{self.__class__.__name__}({self.ref}) where get_referenced returns {self.get_referenced().__class__.__name__} instance"


class ListDynamicallyReferenced(ConfigHierarchy):
    refs: List[DynamicallyReferenced]
