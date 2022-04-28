import inspect
import re
import typing
from configparser import RawConfigParser
from pathlib import Path

from pydantic import BaseModel
from pydantic.fields import SHAPE_LIST, SHAPE_SINGLETON, SHAPE_TUPLE, SHAPE_ITERABLE, SHAPE_SEQUENCE, \
    SHAPE_TUPLE_ELLIPSIS, SHAPE_SET, SHAPE_FROZENSET
from pydantic.main import ModelMetaclass
from pydantic.utils import lenient_issubclass

from config_wrangler.config_data_loaders.file_config_data_loader import FileConfigDataLoader
from config_wrangler.utils import full_name


class IniConfigDataLoader(FileConfigDataLoader):
    def _read_file(self, file_path: Path) -> typing.MutableMapping:
        self.log.debug(f"Reading {file_path}")
        self.files_read.append(file_path)
        config_data = RawConfigParser()
        config_data.read(file_path, encoding='utf8')
        config_data_dict = {section: {key: val for key, val in config_data.items(section)} for section in config_data.sections()}

        return config_data_dict

    def save_empty_config_data(self, config_model: BaseModel):
        file_path = Path(self.start_path, self.file_name)

        with file_path.open('wt') as config_file:
            logging_re = re.compile(r'typing.Dict[str, (\W+.)*LogLevel]')
            app_config_signature = inspect.signature(config_model)
            for section in app_config_signature.parameters.values():
                if section.name[0] != '_':
                    print(f"[{section.name}]", file=config_file)
                    if isinstance(section.annotation, ModelMetaclass):
                        for val in inspect.signature(section.annotation).parameters.values():
                            if val.default != val.empty:
                                print(f"; {val.name} = {val.default}", file=config_file)
                            else:
                                print(f"{val.name} = {val.annotation.__name__}_value_needed_here", file=config_file)
                    elif logging_re.match(str(section.annotation)):
                        print(f"root = INFO", file=config_file)
                        print(f"__main__=DEBUG", file=config_file)
                        print(f"requests=INFO", file=config_file)
                        print(f"; etc for each module that needs a unique log level", file=config_file)
                    elif str(section.annotation).startswith('typing.Dict[str, '):
                        print(f"; {str(section.annotation)}", file=config_file)
                        print(f"; setting1 = value", file=config_file)
                        print(f"; setting2 = value", file=config_file)
                        print(f"; etc", file=config_file)
                    else:
                        raise ValueError(f"ERROR {section} is a {section.annotation} instead of ModelMetaclass")
                print("", file=config_file)
        self.log.info(f"Created {file_path}")

    def save_config_data(self, config_data: BaseModel):
        file_path = Path(self.start_path, self.file_name)
        config_data_ini_ready = IniConfigDataLoader.prepare_config_data_for_save(config_data)

        with file_path.open('wt') as config_file:
            for section, section_data in config_data_ini_ready.items():
                for field, value in section_data:
                    print(f"{field}={value}", file=config_file)
                print("", file=config_file)
        self.log.info(f"Created {file_path}")

    @staticmethod
    def format_value_for_save(field_value):
        if isinstance(field_value, bytes):
            field_value = field_value.decode('utf8')
        else:
            field_value = str(field_value)
        return field_value

    @staticmethod
    def prepare_config_data_for_save(
            config: BaseModel,
            default_delimiter='\n',
            parents=None,
            root_config_data: typing.MutableMapping = None
    ) -> dict:
        if parents is None:
            parents = []
        config_data_dict = config.dict()
        if root_config_data is None:
            root_config_data = config_data_dict
        for field in config.__fields__.values():
            field_value = config_data_dict[field.alias]
            if field.shape == SHAPE_SINGLETON and lenient_issubclass(field.type_, BaseModel):
                section_data = IniConfigDataLoader.prepare_config_data_for_save(
                    config=getattr(config, field.alias),
                    parents=parents + [field.alias],
                    default_delimiter=default_delimiter,
                    root_config_data=root_config_data,
                )
                if len(parents) == 0:
                    root_config_data[field.alias] = section_data
                else:
                    # Flatten to 2 levels (section + field=value)
                    section_name = full_name(parents, field.alias)
                    root_config_data[section_name] = section_data

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
                        root_config_data[sub_section_id] = IniConfigDataLoader.prepare_config_data_for_save(
                            config=sub_section_value,
                            parents=None,
                            default_delimiter=default_delimiter,
                            root_config_data=root_config_data,
                        )
                    config_data_dict[field.alias] = section_name_list
                else:
                    value_list = [IniConfigDataLoader.format_value_for_save(v) for v in field_value]
                    delimiter = field.field_info.extra.get('delimiter', default_delimiter)
                    config_data_dict[field.alias] = delimiter.join(value_list)
            elif (
                    field.shape in {SHAPE_SET, SHAPE_FROZENSET}
                    or field.type_ in {set, frozenset}
            ):
                value_list = [IniConfigDataLoader.format_value_for_save(v) for v in field_value]
                delimiter = field.field_info.extra.get('delimiter', default_delimiter)
                config_data_dict[field.alias] = delimiter.join(value_list)
            else:
                # Use python format
                config_data_dict[field.alias] = IniConfigDataLoader.format_value_for_save(field_value)

        return config_data_dict
