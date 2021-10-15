import typing
from datetime import date, datetime, time
from enum import Enum
from pathlib import Path

from pydantic import BaseModel
from pydantic.fields import SHAPE_LIST, SHAPE_SINGLETON, SHAPE_TUPLE, SHAPE_ITERABLE, SHAPE_SEQUENCE, \
    SHAPE_TUPLE_ELLIPSIS, SHAPE_SET, SHAPE_FROZENSET
from pydantic.utils import lenient_issubclass

from config_wrangler.config_data_loaders.file_config_data_loader import FileConfigDataLoader


class TomlConfigDataLoader(FileConfigDataLoader):
    def __init__(
            self,
            file_name: str,
            start_path: typing.Optional[str] = None,
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

    def _read_file(self, file_path: Path) -> typing.MutableMapping:
        self.log.debug(f"Reading {file_path}")
        self.files_read.append(file_path)
        with file_path.open('rt', encoding='utf8') as toml_content:
            config_data = self.toml.load(toml_content)
        return config_data

    def save_config_data(self, config_data: BaseModel):
        file_path = Path(self.start_path, self.file_name)
        config_data_toml_ready = TomlConfigDataLoader.prepare_config_data(config_data)
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
    def prepare_config_data(config: BaseModel, default_delimiter='\n', parents=None) -> dict:
        if parents is None:
            parents = []
        toml_data_dict = config.dict()
        for field in config.__fields__.values():
            field_value = toml_data_dict[field.alias]
            if field.shape == SHAPE_SINGLETON and lenient_issubclass(field.type_, BaseModel):
                toml_data_dict[field.alias] = TomlConfigDataLoader.prepare_config_data(
                    getattr(config, field.alias),
                    parents=parents + [field.alias]
                )
            elif (
                    field.shape in {SHAPE_LIST, SHAPE_TUPLE, SHAPE_TUPLE_ELLIPSIS, SHAPE_ITERABLE, SHAPE_SEQUENCE}
                    or field.type_ in {list, tuple}
            ):
                create_from_section_names = field.field_info.extra.get('create_from_section_names', False)
                if create_from_section_names:
                    section_name_list = []
                    for sub_section_number, sub_section_value in enumerate(getattr(config, field.alias)):
                        sub_section_id = f"{field.alias}_{sub_section_number}"
                        section_name_list.append(sub_section_id)
                        toml_data_dict[sub_section_id] = TomlConfigDataLoader.prepare_config_data(
                            sub_section_value,
                        )
                    toml_data_dict[field.alias] = section_name_list
                else:
                    value_list = [TomlConfigDataLoader.format_value_for_save(v) for v in field_value]
                    toml_data_dict[field.alias] = value_list
            elif (
                    field.shape in {SHAPE_SET, SHAPE_FROZENSET}
                    or field.type_ in {set, frozenset}
            ):
                value_list = [TomlConfigDataLoader.format_value_for_save(v) for v in field_value]
                toml_data_dict[field.alias] = value_list
            else:
                # Use python format
                toml_data_dict[field.alias] = TomlConfigDataLoader.format_value_for_save(field_value)

        return toml_data_dict
