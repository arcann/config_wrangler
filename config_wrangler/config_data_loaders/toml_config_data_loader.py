from datetime import date, datetime, time
from enum import Enum
from pathlib import Path
from typing import *

from pydantic import BaseModel

from config_wrangler.config_data_loaders.file_config_data_loader import FileConfigDataLoader
from config_wrangler.config_types.dynamically_referenced import ListDynamicallyReferenced
from config_wrangler.utils import lenient_issubclass


class TomlConfigDataLoader(FileConfigDataLoader):
    def __init__(
            self,
            file_name: str,
            start_path: Optional[str] = None,
    ):
        super().__init__(
            start_path=start_path,
            file_name=file_name,
        )
        try:
            import toml
        except ImportError:
            raise RuntimeError(f"Module toml required for TomlSettingsLoader. "
                               f"Use pip install toml or poetry add toml as appropriate.")
        self.toml = toml

    def _read_file(self, file_path: Path) -> MutableMapping:
        self.log.info(f"Reading {file_path}")
        self.files_read.append(file_path)
        with file_path.open('rt', encoding='utf8') as toml_content:
            config_data = self.toml.load(toml_content)
        return config_data

    def save_config_data(self, config_data: BaseModel):
        file_path = Path(self.start_path, self.file_name)
        config_data_toml_ready = TomlConfigDataLoader.prepare_config_data_for_save(config_data)
        with file_path.open('wt', encoding='utf8') as config_file:
            config_file.write(self.toml.dumps(config_data_toml_ready))
        self.log.info(f"Created {file_path}")

    @staticmethod
    def format_value_for_save(field_value):
        if isinstance(field_value, bool):
            pass
        elif isinstance(field_value, int):
            pass
        elif isinstance(field_value, float):
            pass
        elif isinstance(field_value, datetime):
            pass
        elif isinstance(field_value, date):
            pass
        elif isinstance(field_value, time):
            pass
        elif isinstance(field_value, bytes):
            field_value = field_value.decode('utf8')
        elif isinstance(field_value, Path):
            field_value = str(field_value)
        elif isinstance(field_value, Enum):
            field_value = str(field_value)
        elif isinstance(field_value, dict):
            str_keys = True
            for key, value in field_value.items():
                if not isinstance(key, str):
                    str_keys = False
                field_value[key] = TomlConfigDataLoader.format_value_for_save(value)
            if not str_keys:
                field_value = str(field_value)
            else:
                pass
        else:
            field_value = str(field_value)
        return field_value

    @staticmethod
    def prepare_config_data_for_save(config: BaseModel, default_delimiter='\n', parents=None) -> dict:
        if parents is None:
            parents = []
        config_data_dict = config.model_dump()
        for field_name, field_info in config.model_fields.items():
            field_name = field_info.alias or field_name
            field_value = config_data_dict[field_name]
            if lenient_issubclass(field_info.annotation, BaseModel):
                config_data_dict[field_name] = TomlConfigDataLoader.prepare_config_data_for_save(
                    getattr(config, field_name),
                    parents=parents + [field_name]
                )
            elif lenient_issubclass(field_info.annotation, ListDynamicallyReferenced):
                section_name_list = []
                for sub_section_number, sub_section_value in enumerate(getattr(config, field_name)):
                    sub_section_id = f"{field_name}_{sub_section_number}"
                    section_name_list.append(sub_section_id)
                    config_data_dict[sub_section_id] = TomlConfigDataLoader.prepare_config_data_for_save(
                        sub_section_value,
                    )
                config_data_dict[field_name] = section_name_list
            elif lenient_issubclass(field_info.annotation, List):
                value_list = [TomlConfigDataLoader.format_value_for_save(v) for v in field_value]
                config_data_dict[field_name] = value_list
            elif lenient_issubclass(field_info.annotation, Set):
                value_list = [TomlConfigDataLoader.format_value_for_save(v) for v in field_value]
                config_data_dict[field_name] = value_list
            else:
                # Use python format
                config_data_dict[field_name] = TomlConfigDataLoader.format_value_for_save(field_value)

        return config_data_dict
