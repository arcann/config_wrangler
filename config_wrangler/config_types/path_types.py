import os
import shutil
from pathlib import Path
from typing import Any

from pydantic import DirectoryPath, FilePath, BeforeValidator
from typing_extensions import Annotated

# Make sure these can be imported from here and not just from pydantic
DirectoryPath = DirectoryPath
FilePath = FilePath


def _path_validator(value: Any) -> Path:
    return Path(value)


def _file_validator(p: Path) -> Path:
    if not p.is_file():
        raise ValueError(f"{p} is not a directory")
    return p


def _directory_validator(p: Path) -> Path:
    if not p.is_dir():
        raise ValueError(f"{p} is not a directory")
    return p


def _expand_user_validator(p: Path) -> Path:
    return p.expanduser()


def _path_exists(p: Path) -> Path:
    if not p.exists():
        raise ValueError(f"Could not find path {p}")
    return p


def _ensure_exists_validator(p: Path) -> Path:
    if not p.exists():
        p.mkdir(parents=True, exist_ok=True)
        if not p.exists():
            raise ValueError(f"Could not create directory {p}")
    return p


def _find_up(path: Path) -> Path:
    if path.exists():
        return path
    else:
        start_dir = Path(os.getcwd())
        for parent_dir in start_dir.parents:
            parent_path = parent_dir / path
            if parent_path.exists():
                return parent_path
        raise ValueError(f"{path} not found in {start_dir} or parents")


def _find_in_system_path(path: Path) -> Path:
    full_path = shutil.which(str(path))
    if full_path is None:
        raise ValueError(f"{path} not found")
    # Note: on Windows any existing file appears as executable
    elif not os.access(full_path, os.X_OK):
        raise ValueError(f"{path} found at {full_path} but is not executable")
    return Path(full_path)


PathExpandUser = Annotated[
    Path,
    BeforeValidator(_path_exists),
    BeforeValidator(_expand_user_validator),
    BeforeValidator(_path_validator)
]


DirectoryExpandUser = Annotated[
    Path,
    BeforeValidator(_directory_validator),
    BeforeValidator(_expand_user_validator),
    BeforeValidator(_path_validator)
]


AutoCreateDirectoryPath = Annotated[
    Path,
    BeforeValidator(_directory_validator),
    BeforeValidator(_ensure_exists_validator),
    BeforeValidator(_expand_user_validator),
    BeforeValidator(_path_validator)
]


PathFindUp = Annotated[
    Path,
    BeforeValidator(_find_up),
    BeforeValidator(_path_validator)
]


DirectoryFindUp = Annotated[
    Path,
    BeforeValidator(_directory_validator),
    BeforeValidator(_find_up),
    BeforeValidator(_path_validator)
]

PathFindUpExpandUser = Annotated[
    Path,
    BeforeValidator(_find_up),
    BeforeValidator(_expand_user_validator),
    BeforeValidator(_path_validator)
]

DirectoryFindUpExpandUser = Annotated[
    Path,
    BeforeValidator(_directory_validator),
    BeforeValidator(_find_up),
    BeforeValidator(_expand_user_validator),
    BeforeValidator(_path_validator)
]


ExecutablePath = Annotated[
    Path,
    BeforeValidator(_file_validator),
    BeforeValidator(_find_in_system_path),
    BeforeValidator(_path_validator)
]
