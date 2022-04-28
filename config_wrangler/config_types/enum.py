from strenum import StrEnum
from enum import auto


def auto_str():
    # noinspection PyArgumentList
    return auto()


__all__ = ['StrEnum', 'auto_str']

# Convenience module so that enum configs don't have to do imports from two locations
