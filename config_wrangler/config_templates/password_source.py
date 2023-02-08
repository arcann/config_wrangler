from enum import auto
from strenum import StrEnum


class PasswordSource(StrEnum):
    CONFIG_FILE = auto()
    KEYRING = auto()
    KEEPASS = auto()
