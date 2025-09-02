from enum import auto
from typing import Annotated, Any

from strenum import StrEnum


class PasswordSource(StrEnum):
    CONFIG_FILE = auto()
    ENVIRONMENT = auto()
    KEYRING = auto()
    KEEPASS = auto()
    AWS_ASSUME_ROLE = auto()


def _check_password_source(value: Any) -> PasswordSource:
    if isinstance(value, str):
        value = value.upper()
    return PasswordSource[value]


PasswordSourceValidated = Annotated[
    PasswordSource,
    _check_password_source,
]