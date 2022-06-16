import os
import shutil
from pathlib import Path
from pydantic import DirectoryPath, FilePath
from pydantic.validators import path_validator
from auto_all import public


@public
class PathExpandUser(FilePath):
    @staticmethod
    def _expand_user(path: Path):
        path = path.expanduser()
        return path

    @classmethod
    def __get_validators__(cls):
        yield path_validator
        yield cls._expand_user
        yield from super().__get_validators__()


@public
class DirectoryExpandUser(PathExpandUser, DirectoryPath):
    @classmethod
    def __get_validators__(cls):
        yield path_validator
        yield cls._expand_user
        yield DirectoryPath.validate


@public
class AutoCreateDirectory(DirectoryExpandUser):
    @staticmethod
    def _ensure_exsits(path: Path):
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
            if not path.exists():
                raise ValueError(f"Could not create directory {path}")
        return path

    @classmethod
    def __get_validators__(cls):
        yield path_validator
        yield cls._expand_user
        yield cls._ensure_exsits
        yield from super().__get_validators__()


@public
class AutoCreateDirectoryPath(AutoCreateDirectory):
    pass
    # Will be deprecated


@public
class PathFindUp(FilePath):
    @staticmethod
    def _find_up(path: Path):
        if path.exists():
            return path
        else:
            start_dir = Path(os.getcwd())
            for parent_dir in start_dir.parents:
                parent_path = parent_dir / path
                if parent_path.exists():
                    return parent_path
            raise ValueError(f"{path} not found in {start_dir} or parents")

    @classmethod
    def __get_validators__(cls):
        yield path_validator
        yield cls._find_up


@public
class DirectoryFindUp(PathFindUp, DirectoryPath):
    @classmethod
    def __get_validators__(cls):
        yield path_validator
        yield cls._find_up
        yield DirectoryPath.validate


@public
class PathFindUpExpandUser(DirectoryFindUp, PathExpandUser):
    @classmethod
    def __get_validators__(cls):
        yield path_validator
        yield cls._expand_user
        yield cls._find_up


@public
class DirectoryFindUpExpandUser(DirectoryFindUp, PathExpandUser):
    @classmethod
    def __get_validators__(cls):
        yield path_validator
        yield cls._expand_user
        yield cls._find_up


@public
class ExecutablePath(Path):
    @staticmethod
    def __find_in_system_path(path: Path):
        full_path = shutil.which(str(path))
        if full_path is None:
            raise ValueError(f"{path} not found")
        # Note: on Windows any existing file appears as executable
        elif not os.access(full_path, os.X_OK):
            raise ValueError(f"{path} found at {full_path} but is not executable")
        return Path(full_path)

    @classmethod
    def __get_validators__(cls):
        yield path_validator
        yield cls.__find_in_system_path
