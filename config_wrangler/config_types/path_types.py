import os
import shutil
from pathlib import Path
from pydantic import DirectoryPath, FilePath
from pydantic.validators import path_validator

__all__ = [
    'FilePath',
    'DirectoryPath',
    'AutoCreateDirectoryPath',
    'DirectoryFindUp',
    'PathExpandUser',
    'ExecutablePath',
]


class PathExpandUser(DirectoryPath):
    @staticmethod
    def _expand_user(path: Path):
        path = path.expanduser()
        return path

    @classmethod
    def __get_validators__(cls):
        yield path_validator
        yield cls._expand_user
        super().__get_validators__()


class AutoCreateDirectoryPath(PathExpandUser):
    @staticmethod
    def _ensure_exsits(path: Path):
        if not path.exists():
            os.makedirs(path)
        return path

    @classmethod
    def __get_validators__(cls):
        yield path_validator
        yield cls._expand_user
        yield cls._ensure_exsits
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


class ExecutablePath(Path):
    @staticmethod
    def __find_in_system_path(path: Path):
        full_path = shutil.which(path)
        if full_path is None:
            raise FileNotFoundError(f"{path} not found")
        # Note: on Windows any existing file appears as executable
        elif not os.access(path, os.X_OK):
            raise ValueError(f"{path} found but is not executable")

    @classmethod
    def __get_validators__(cls):
        yield path_validator
        yield cls.__find_in_system_path
