import ast
import json
import logging
import re
import typing
from datetime import timezone, datetime

from pydantic import BaseModel
from pydantic.fields import SHAPE_LIST, SHAPE_SINGLETON, SHAPE_TUPLE, SHAPE_ITERABLE, SHAPE_SEQUENCE, \
    SHAPE_TUPLE_ELLIPSIS, SHAPE_SET, SHAPE_FROZENSET, SHAPE_DICT, SHAPE_DEFAULTDICT, Field
from pydantic.utils import lenient_issubclass

from config_wrangler.config_exception import ConfigError


class TZFormatter(logging.Formatter):
    local_timezone = datetime.now(timezone.utc).astimezone().tzinfo

    @staticmethod
    def tz_aware_converter(timestamp) -> datetime:
        return datetime.fromtimestamp(timestamp, TZFormatter.local_timezone)

    def formatTime(self, record, datefmt=None):
        dt = TZFormatter.tz_aware_converter(record.created)
        if datefmt is not None:
            result = dt.strftime(datefmt)
        else:
            time_part = dt.strftime(self.default_time_format)
            result = self.default_msec_format % (time_part, record.msecs)
        return result


def merge_configs(child: typing.MutableMapping, parent: typing.MutableMapping) -> None:
    for section in parent:
        if section not in child:
            child[section] = parent[section]
        else:
            if isinstance(child[section], typing.MutableMapping):
                merge_configs(child[section], parent[section])
            else:
                pass


def resolve_variable(root_config_data: typing.MutableMapping, variable_name: str, default=None, part_delimiter=':') -> typing.Any:
    variable_name_parts = variable_name.split(part_delimiter)
    result = root_config_data
    for part in variable_name_parts:
        if part in result:
            result = result[part]
        else:
            return default
    return result


_interpolation_re = re.compile(r"\${([^}]+)}")


def interpolate_values(container: typing.MutableMapping, root_config_data: typing.MutableMapping):
    for section in container:
        value = container[section]
        if isinstance(value, typing.MutableMapping):
            interpolate_values(value, root_config_data=root_config_data)
        elif isinstance(value, str):
            if '$' in value:
                variables_cnt = 0
                result_values = []
                next_start = 0
                for variable_found in _interpolation_re.finditer(value):
                    variables_cnt += 1
                    variable_name = variable_found.groups()[0]
                    variable_text = f"${{{variable_name}}}"
                    var_start, var_end = variable_found.span()

                    if ':' in variable_name:
                        variable_replacement = resolve_variable(
                            root_config_data, variable_name, default=variable_text, part_delimiter=':'
                        )
                    elif '.' in variable_name:
                        variable_replacement = resolve_variable(
                            root_config_data, variable_name, default=variable_text, part_delimiter='.'
                        )
                    else:
                        variable_replacement = container.get(variable_name, default=variable_text)

                    result_values.append(value[next_start:var_start])
                    result_values.append(variable_replacement)
                    next_start = var_end + 1
                if variables_cnt > 0:
                    if next_start < len(value):
                        result_values.append(value[next_start:])
                    container[section] = ''.join(result_values)


def parse_as_literal_or_json(value: str) -> typing.Any:
    try:
        return ast.literal_eval(value)
    except (ValueError, SyntaxError) as el:
        try:
            return json.loads(value)
        except ValueError as ej:
            raise ConfigError(
                f"Value {value} could not be parsed as python literal '{el}' or json '{ej}'"
            )


def parse_delimited_list(field: Field, value: str) -> typing.Sequence:
    value = value.strip()
    if len(value) == 0:
        return []
    delimiter = field.field_info.extra.get('delimiter', None)
    if delimiter is None and value[0] not in {'[', '{'}:
        # Try to automatically recognize the delimiter
        for delimiter in [',', '\n', '|']:
            if delimiter in value:
                break
    if delimiter is not None:
        if value[0] == delimiter:
            value = value[1:]
        result = [v.strip() for v in value.split(delimiter)]
        if field.type_ == int:
            result = [int(v) for v in result]
        elif field.type_ == float:
            result = [float(v) for v in result]
    else:
        try:
            result = parse_as_literal_or_json(value)
        except ValueError as e:
            raise ConfigError(f"Field {field.alias} {e}")
    return result


def full_name(parents: typing.List[str], field_name: str):
    return '.'.join(parents + [field_name])


def match_config_data_to_model(model: BaseModel, config_data: typing.MutableMapping, root_config_data: typing.MutableMapping = None, parents=None):
    if parents is None:
        parents = []
    if root_config_data is None:
        root_config_data = config_data

    # Make mappings from lower case names to actual config field names
    config_name_map = {key.lower(): key for key in config_data}
    root_config_name_map = {key.lower(): key for key in root_config_data}

    # Scan all model fields to look for values in the MutableMapping
    for field in model.__fields__.values():
        # Check for either a direct name match or a case in-sensitive match
        field_lower = field.alias.lower()
        if field.alias in config_data:
            found = True
        elif field_lower in config_name_map:
            found = True
            field_name = config_name_map[field_lower]
            config_data[field.alias] = config_data[field_name]
            del config_data[field_name]
        else:
            found = False

        # Check for nested objects set using top level dotted names (e.g. [parent.child])
        # (either a direct name match or a case in-sensitive match)
        if not found and len(parents) > 0:
            section_name = '.'.join(parents + [field.alias])
            section_name_lower = section_name.lower()
            if section_name in root_config_data:
                found = True
                config_data[field.alias] = root_config_data[section_name]
            elif section_name_lower in root_config_name_map:
                found = True
                section_name = root_config_name_map[section_name_lower]
                config_data[field.alias] = root_config_data[section_name]

        if found:
            # Check if we should recurse into deeper structures or parse strings into structures
            value = config_data[field.alias]
            if lenient_issubclass(field.type_, BaseModel) or hasattr(field.type_, '__fields__'):
                create_from_section_names = field.field_info.extra.get('create_from_section_names', False)
                if create_from_section_names:
                    inherit = field.field_info.extra.get('inherit', False)
                    if isinstance(value, str):
                        section_names = parse_delimited_list(field, value)
                    else:
                        section_names = value
                    section_contents = []
                    for section in section_names:
                        if isinstance(section, str):
                            if section in root_config_data:
                                if inherit:
                                    for inherit_key, inherit_value in config_data.items():
                                        if inherit_key not in root_config_data[section]:
                                            root_config_data[section][inherit_key] = inherit_value
                                match_config_data_to_model(field.type_, root_config_data[section], root_config_data=root_config_data, parents=parents + [field.alias])
                                section_contents.append(root_config_data[section])
                            elif section in config_data:
                                if inherit:
                                    for inherit_key, inherit_value in config_data.items():
                                        if inherit_key not in config_data[section] and inherit_key != field.alias and inherit_key not in section_names:
                                            config_data[section][inherit_key] = inherit_value
                                match_config_data_to_model(field.type_, config_data[section], root_config_data=root_config_data, parents=parents + [field.alias])
                                section_contents.append(config_data[section])
                            else:
                                raise ConfigError(f"{full_name(parents, field.alias)} refers to section {section} which does not exist.")
                        else:
                            # Not string, assume it's already the section contents
                            section_contents.append(section)
                    config_data[field.alias] = section_contents
                else:
                    match_config_data_to_model(field.type_, config_data[field.alias], root_config_data=root_config_data, parents=parents + [field.alias])
            elif (
                    field.shape in {SHAPE_LIST, SHAPE_TUPLE, SHAPE_TUPLE_ELLIPSIS, SHAPE_ITERABLE, SHAPE_SEQUENCE}
                    or field.type_ in {list, tuple}
            ):
                if isinstance(value, str):
                    config_data[field.alias] = parse_delimited_list(field, value)
            elif (
                    field.shape in {SHAPE_SET}
                    or field.type_ in {set}
            ):
                if isinstance(value, str):
                    config_data[field.alias] = set(parse_delimited_list(field, value))
            elif (
                    field.shape in {SHAPE_FROZENSET}
                    or field.type_ in {frozenset}
            ):
                if isinstance(value, str):
                    config_data[field.alias] = frozenset(parse_delimited_list(field, value))
            elif (
                    field.shape in {SHAPE_DICT, SHAPE_DEFAULTDICT}
                    or field.type_ in {dict}
            ):
                if isinstance(value, str):
                    try:
                        config_data[field.alias] = parse_as_literal_or_json(value)
                    except ValueError as e:
                        raise ConfigError(f"Field {full_name(parents, field.alias)} {e}")
            elif field.shape == SHAPE_SINGLETON:
                if field.type_ == int:
                    config_data[field.alias] = int(config_data[field.alias])
                elif field.type_ == float:
                    config_data[field.alias] = float(config_data[field.alias])
            else:
                pass
                # We'll let pydantic parse it as is




