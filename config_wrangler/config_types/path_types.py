import os
from pathlib import Path
from pydantic import DirectoryPath
from pydantic.validators import path_validator

__all__ = ['DirectoryPath', 'AutoCreateDirectoryPath', 'DirectoryFindUp', 'PathExpandUser']


class PathExpandUser(DirectoryPath):
    @staticmethod
    def __expand_user(path: Path):
        path = path.expanduser()
        return path

    @classmethod
    def __get_validators__(cls):
        yield path_validator
        yield cls.__expand_user
        super().__get_validators__()


class AutoCreateDirectoryPath(DirectoryPath):
    @staticmethod
    def __ensure_exsits(path: Path):
        if not path.exists():
            os.makedirs(path)
        return path

    @classmethod
    def __get_validators__(cls):
        yield path_validator
        yield cls.__ensure_exsits
        super().__get_validators__()


class DirectoryFindUp(DirectoryPath):
    @staticmethod
    def __find_up(path: Path):
        if path.exists():
            return path
        else:
            start_dir = Path(os.getcwd())
            for parent_dir in start_dir.parents:
                parent_path = Path(parent_dir, path)
                if parent_path.exists():
                    return parent_path
            raise FileNotFoundError(f"{path} not found in {start_dir} or parents")

    @classmethod
    def __get_validators__(cls):
        yield path_validator
        yield cls.__find_up
        yield cls.validate
