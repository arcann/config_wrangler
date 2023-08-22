import inspect
from collections import defaultdict
from types import MethodType
from typing import Set

from pydantic import BaseModel

class_registry = defaultdict(set)


def get_class_that_defined_method(method: MethodType) -> str:
    parts = method.__qualname__.split('.')
    return '.'.join(parts[:-1])


def config_hierarchy_validator(validation_fn: MethodType):
    # validation_fn._is_config_hierarchy_validator = True

    def decorated_validator(*args, **kwargs):
        validation_fn(*args, **kwargs)

    decorated_validator._is_config_hierarchy_validator = True
    return decorated_validator


def get_validation_functions(model_level: BaseModel) -> Set[str]:
    return class_registry.get(model_level.__class__.__qualname__, set())
