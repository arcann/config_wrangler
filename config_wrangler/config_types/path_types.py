import os
from pathlib import Path
from pydantic import DirectoryPath
from pydantic.validators import path_validator

__all__ = ['DirectoryPath', 'AutoCreateDirectoryPath']


class AutoCreateDirectoryPath(DirectoryPath):
    @staticmethod
    def __ensure_exsits(path: Path):
        if not path.exists():
            os.makedirs(path)
        return path

    @classmethod
    def __get_validators__(cls):
        yield path_validator
        yield AutoCreateDirectoryPath.__ensure_exsits
        yield cls.validate
