from pydantic import validator

from config_wrangler.config_templates.config_hierarchy import ConfigHierarchy


class DynamicallyReferenced(ConfigHierarchy):
    ref: str

    @validator('ref')
    def _validate_phase_1(cls, value):
        if value == '':
            raise ValueError('Blank is not valid for a DynamicallyReferenced section')
        return value

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
                    raise ValueError(f"{self.ref} not found.")
            return model

    def __str__(self):
        return f"{self.ref}"

    def __repr__(self):
        return f"{self.__class__.__name__}({self.ref}) where get_referenced returns {self.get_referenced().__class__.__name__} instance"
