import os
import typing
from copy import deepcopy
from pathlib import Path

from pydantic import BaseModel

from config_wrangler.config_data_loaders.base_config_data_loader import BaseConfigDataLoader
from config_wrangler.utils import merge_configs, match_config_data_to_model


class FileConfigDataLoader(BaseConfigDataLoader):
    config_inheritance_section: str = 'Config'
    config_inheritance_field_name_prefix: str = 'parent'

    def __init__(
            self,
            file_name: str,
            start_path: typing.Optional[str] = None,
    ):
        super().__init__()
        self.start_path = start_path or os.getcwd()
        self.file_name = file_name
        self.files_read = []

    def _read_file(self, file_path: Path) -> typing.MutableMapping:
        raise NotImplementedError()

    def _merge_files_into_config_data(self, config_data: typing.MutableMapping, path: Path, file_name: str, fail_on_does_not_exist: bool = True):
        full_path = Path(file_name)
        if not full_path.is_absolute():
            full_path = Path(path, file_name)

        if full_path.exists():
            file_config_data = self._read_file_plus_inherited(full_path)
            # Check for and remove any [Config] parent settings.
            # They should have already been used, but we don't want to merge them up
            if self.config_inheritance_section in file_config_data:
                for field_name in list(file_config_data[self.config_inheritance_section]):
                    if field_name.startswith(self.config_inheritance_field_name_prefix):
                        del file_config_data[self.config_inheritance_section][field_name]
            merge_configs(config_data, file_config_data)
        elif fail_on_does_not_exist:
            raise FileNotFoundError(f"{file_name} not found with path = {path}")
        return config_data

    def _check_inherited_files(
            self,
            config_data: typing.MutableMapping,
            path: Path,

    ) -> typing.MutableMapping:
        if self.config_inheritance_section in config_data:
            for field_name in config_data[self.config_inheritance_section]:
                if field_name.startswith(self.config_inheritance_field_name_prefix):
                    file_name = config_data[self.config_inheritance_section][field_name]
                    if '\n' in file_name:
                        for file_name_part in file_name.split('\n'):
                            self._merge_files_into_config_data(config_data, path, file_name_part)
                    else:
                        self._merge_files_into_config_data(config_data, path, file_name)
        return config_data

    def _read_file_plus_inherited(self, file_path: Path):
        file_config_data = self._read_file(file_path)
        folder = file_path.parents[0]
        with_parents_added = self._check_inherited_files(file_config_data, path=folder)
        return with_parents_added

    def read_config_data(self, model: BaseModel) -> typing.MutableMapping:
        full_path = Path(self.start_path, self.file_name)

        config_data = deepcopy(self._init_config_data)

        if full_path.exists():
            file_config_data = self._read_file_plus_inherited(full_path)
            merge_configs(config_data, file_config_data)

        for parent_dir in full_path.parents:
            parent_path = Path(parent_dir, self.file_name)
            if parent_path != full_path:
                if parent_path.exists():
                    file_config_data = self._read_file_plus_inherited(parent_path)
                    merge_configs(config_data, file_config_data)

        if len(self.files_read) == 0:
            raise FileNotFoundError(f"{full_path} or {self.file_name} in parent directories")

        match_config_data_to_model(model, config_data)
        return config_data
