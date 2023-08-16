import ast
import inspect
import json
import logging
import re
import types
from datetime import timezone, datetime
from typing import *

from pydantic import BaseModel
from pydantic.fields import FieldInfo
from pydicti import dicti, Dicti

from config_wrangler.config_exception import ConfigError
from config_wrangler.config_types.delimited_field import DelimitedListFieldInfo
from config_wrangler.config_types.dynamically_referenced import DynamicallyReferenced, ListDynamicallyReferenced


# Moved here because  Pydantic V2 depracated it
def lenient_issubclass(
        cls: Any,
        class_or_tuple: Union[Type[Any], Tuple[Type[Any], ...], Set[Type[Any]], None]
) -> bool:
    try:
        if isinstance(class_or_tuple, set):
            class_or_tuple = tuple(class_or_tuple)

        if isinstance(cls, type):
            return issubclass(cls, class_or_tuple)
        else:
            try:
                origin = cls.__origin__
            except AttributeError:
                origin = get_origin(cls)
            if origin is not None:
                if origin == Union:
                    for union_cls in get_args(class_or_tuple):
                        if issubclass(union_cls, class_or_tuple):
                            return True
                else:
                    return issubclass(origin, class_or_tuple)

    except TypeError:
        if isinstance(cls, (types.GenericAlias, types.UnionType)):
            return False
        raise


def has_sub_fields(field_info: FieldInfo):
    return hasattr(field_info.annotation, 'model_fields')


def get_one_sub_field(field_info: FieldInfo) -> Tuple[str, FieldInfo]:
    try:
        # noinspection PyUnresolvedReferences
        model_fields = field_info.annotation.model_fields
    except AttributeError:
        raise ValueError(f"{field_info} is not a sub model")
    fields_list = list(model_fields.keys())
    if len(fields_list) != 1:
        raise ValueError(f"{field_info} has more than one field {fields_list}")
    return fields_list[0], model_fields[fields_list[0]]


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


def merge_configs(child: MutableMapping, parent: MutableMapping) -> None:
    for section in parent:
        if section not in child:
            child[section] = parent[section]
        else:
            if isinstance(child[section], MutableMapping):
                merge_configs(child[section], parent[section])
            else:
                pass


def resolve_variable(root_config_data: MutableMapping, variable_name: str, part_delimiter=':') -> Any:
    variable_name_parts = variable_name.split(part_delimiter)
    result = root_config_data
    for part in variable_name_parts:
        # Change to case-insensitive dict
        if not isinstance(result, dicti):
            result = Dicti(result)

        if part in result:
            result = result[part]
        else:
            raise ValueError(f"<<{part} NOT FOUND when resolving variable with parts: {variable_name_parts}>>")
    return result


_interpolation_re = re.compile(r"\${([^}]+)}")


def interpolate_values(container: MutableMapping, root_config_data: MutableMapping) -> List[Tuple[str, str]]:
    errors = []
    for section in container:
        value = container[section]
        if isinstance(value, MutableMapping):
            sub_errors = interpolate_values(value, root_config_data=root_config_data)
            errors.extend(sub_errors)
        elif isinstance(value, str):
            if '$' in value:
                depth = 0
                done = False
                new_value = value
                while not done:
                    done = True
                    depth += 1
                    variables_cnt = 0
                    result_values = []
                    next_start = 0
                    for variable_found in _interpolation_re.finditer(new_value):
                        variables_cnt += 1
                        variable_name = variable_found.groups()[0]
                        var_start, var_end = variable_found.span()

                        part_delimiter = None
                        if ':' in variable_name:
                            part_delimiter = ':'

                        elif '.' in variable_name:
                            part_delimiter = '.'

                        variable_replacement = 'ERROR'
                        if part_delimiter is not None:
                            try:
                                variable_replacement = resolve_variable(
                                    root_config_data,
                                    variable_name,
                                    part_delimiter=part_delimiter,
                                )
                            except ValueError as e:
                                errors.append((section, str(e),))
                        else:
                            try:
                                # Change to case-insensitive dict
                                search_container = Dicti(container)
                                variable_replacement = search_container[variable_name]
                            except KeyError:
                                errors.append((section, f"<<{variable_name} NOT FOUND>>",))

                        result_values.append(new_value[next_start:var_start])
                        result_values.append(variable_replacement)
                        next_start = var_end
                    if variables_cnt > 0:
                        if next_start < len(new_value):
                            result_values.append(new_value[next_start:])
                        new_value = ''.join(result_values)

                        if depth < 50:
                            done = False
                        else:
                            raise ValueError(f"Interpolation recursion depth limit reached on value {value} ended with {new_value}")
                container[section] = new_value
    return errors


def parse_as_literal_or_json(value: str) -> Any:
    try:
        return ast.literal_eval(value)
    except (ValueError, SyntaxError) as el:
        try:
            return json.loads(value)
        except ValueError as ej:
            raise ConfigError(
                f"Value {value} could not be parsed as python literal '{el}' or json '{ej}'"
            )


def parse_delimited_list(
    field_name: str,
    field_info: FieldInfo,
    field_value: str
) -> Sequence:
    value = field_value.strip()
    if len(value) == 0:
        return []

    if isinstance(field_info, DelimitedListFieldInfo):
        delimiter = field_info.delimiter
    else:
        delimiter = None

    if delimiter is None and value[0] not in {'[', '{'}:
        # Try to automatically recognize the delimiter
        for try_delimiter in ['\n', ',', '|']:
            if try_delimiter in value:
                delimiter = try_delimiter
                break
    if delimiter is not None:
        if value[0] == delimiter:
            value = value[1:]
        result = [v.strip() for v in value.split(delimiter)]
        if lenient_issubclass(field_info.annotation, int):
            result = [int(v) for v in result]
        elif lenient_issubclass(field_info.annotation, float):
            result = [float(v) for v in result]
    else:
        try:
            result = parse_as_literal_or_json(value)
        except ValueError as e:
            raise ConfigError(f"Field {field_name} {e}")
    return result


def full_name(parents: List[str], field_name: str):
    return '.'.join(parents + [field_name])


def inherit_fill(parent_config, child_config):
    for inherit_key, inherit_value in parent_config.items():
        if inherit_key not in child_config:
            child_config[inherit_key] = inherit_value


def find_referenced_section(
        field_name: str,
        field_info: FieldInfo,
        parents: List[str],
        section_name: Union[str, MutableMapping],
        current_dict: MutableMapping,
        root_dict: MutableMapping
) -> MutableMapping:
    try:
        # noinspection PyUnresolvedReferences
        inherit = field_info.inherit
    except AttributeError:
        inherit = False
    if isinstance(section_name, str):
        section_value = dict()
        section_name_parts = section_name.split('.')
        parts_used = []
        for parts_to_use in range(len(section_name_parts), 0, -1):
            section_name_2 = '.'.join(section_name_parts[:parts_to_use])
            if section_name_2 in root_dict:
                parts_used.append(tuple(section_name_2,))
                inherit_fill(root_dict[section_name_2], section_value)
            elif section_name_2 in current_dict:
                parts_used.append(tuple(*parents, section_name_2,))
                inherit_fill(current_dict[section_name_2], section_value)
        if inherit:
            inherit_fill(current_dict, section_value)
        if len(parts_used) == 0:
            raise ConfigError(
                f"{full_name(parents, field_name)} refers to section {section_name} which does not exist."
            )
        return section_value
    else:
        return section_name


def match_config_data_to_field(
        field_name: str,
        field_info: FieldInfo,
        field_value: object,
        create_from_section_names: bool,
        parent_container: MutableMapping,
        root_config_data: MutableMapping,
        parents: List[str],
):
    if lenient_issubclass(field_info.annotation, (str, int, float)):
        if create_from_section_names:
            if not hasattr(field_info.annotation, 'model_fields'):
                raise ValueError(f"{full_name(parents, field_name)} has create_from_section_names but has no fields")
            assert isinstance(field_value, str), f"Expected str for {full_name(parents, field_name)} got {type(field_value)} with value {field_value}"
            section_value = find_referenced_section(
                field_name=field_name,
                field_info=field_info,
                parents=parents,
                section_name=field_value,
                current_dict=parent_container,
                root_dict=root_config_data,
            )
            section_value['config_source_name'] = field_value
            field_value = section_value
    elif lenient_issubclass(field_info.annotation, {list, tuple}):
        if isinstance(field_value, str):
            field_value = parse_delimited_list(field_name, field_info, field_value)

        # Conditional change to field_value to obtain value from another config section
        if create_from_section_names:
            if not hasattr(field_info.annotation, 'model_fields'):
                raise ValueError(f"{full_name(parents, field_name)} has create_from_section_names but has no fields")

            section_contents = list()
            for section_name in field_value:
                ref_section_value = find_referenced_section(
                    field_name=field_name,
                    field_info=field_info,
                    parents=parents,
                    section_name=section_name,
                    current_dict=parent_container,
                    root_dict=root_config_data,
                )
                # Transform section_value as needed
                # noinspection PyUnresolvedReferences

                for sub_field_name, sub_field_info in field_info.annotation.model_fields.items():
                    sub_section_value = match_config_data_to_field_or_submodel(
                        field_name=sub_field_name,
                        field_info=sub_field_info,
                        parent_container={sub_field_name: ref_section_value},
                        root_config_data=root_config_data,
                        parents=parents + [field_name, section_name]
                    )
                    ref_section_value[sub_field_name] = sub_section_value
                # Add name to the dict in case the model wants it
                ref_section_value['config_source_name'] = section_name
                section_contents.append(ref_section_value)
            field_value = section_contents
    elif lenient_issubclass(field_info.annotation, dict):
        if isinstance(field_value, str):
            try:
                field_value = parse_as_literal_or_json(field_value)
            except ValueError as e:
                raise ConfigError(f"Field {full_name(parents, field_name)} {e}")

        # Conditional change to field_value to obtain value from another config section
        if create_from_section_names:
            section_contents = dict()
            for key, value in field_value.items():
                if has_sub_fields(field_info):
                    sub_field_name, sub_field_info = get_one_sub_field(field_info)
                    # Transform section_value as needed
                    section_value = match_config_data_to_field(
                        field_name=sub_field_name,
                        field_info=sub_field_info,
                        field_value=value,
                        create_from_section_names=True,
                        parent_container=field_value,
                        root_config_data=root_config_data,
                        parents=parents + [field_name, key, value]
                    )
                    section_contents[key] = section_value
                else:
                    section_value = find_referenced_section(
                        field_name=field_name,
                        field_info=field_info,
                        parents=parents,
                        section_name=value,
                        current_dict=parent_container,
                        root_dict=root_config_data,
                    )
                    section_contents[key] = section_value
            field_value = section_contents
    elif lenient_issubclass(field_info.annotation, set):
        if isinstance(field_value, str):
            field_value = set(
                parse_delimited_list(
                    field_name=field_name,
                    field_info=field_info,
                    field_value=field_value
                )
            )
    elif lenient_issubclass(field_info.annotation, frozenset):
        if isinstance(field_value, str):
            field_value = frozenset(
                parse_delimited_list(
                    field_name=field_name,
                    field_info=field_info,
                    field_value=field_value
                )
            )
    # In all cases not explicitly matched above, we'll let pydantic parse it as is
    return field_value


def match_config_data_to_model(
        model: BaseModel,
        config_data: MutableMapping,
        root_config_data: MutableMapping = None,
        parents=None
):
    if parents is None:
        parents = []
    if root_config_data is None:
        root_config_data = config_data

    # Make mappings from lower case names to actual config field names
    config_name_map = {key.lower(): key for key in config_data}
    root_config_name_map = {key.lower(): key for key in root_config_data}

    # Scan all model fields to look for values in the MutableMapping
    for field_name_outer, field_info in model.model_fields.items():
        # Check for either a direct name match or a case in-sensitive match
        field_name = field_info.alias or field_name_outer
        field_lower = field_name.lower()

        if field_lower in config_data:
            found = True
        elif field_lower in config_name_map:
            found = True
            field_name = config_name_map[field_lower]
            config_data[field_info] = config_data[field_name]
            del config_data[field_name]
        else:
            found = False

        # Check for nested objects set using top level dotted names (e.g. [parent.child])
        # (either a direct name match or a case in-sensitive match)
        if not found and len(parents) > 0:
            section_name = '.'.join(parents + [field_name])
            section_name_lower = section_name.lower()
            if section_name in root_config_data:
                found = True
                # Copy data into place where pydantic will expect it
                config_data[field_name] = root_config_data[section_name]
            elif section_name_lower in root_config_name_map:
                found = True
                section_name = root_config_name_map[section_name_lower]
                # Copy data into place where pydantic will expect it
                config_data[field_name] = root_config_data[section_name]

        if found:
            updated_value = match_config_data_to_field_or_submodel(
                field_name=field_name,
                field_info=field_info,
                parent_container=config_data,
                root_config_data=root_config_data,
                parents=parents + [field_name]
            )
            config_data[field_name] = updated_value
    return config_data


def should_create_from_section_names(field_info: FieldInfo):
    return inspect.isclass(field_info.annotation) and issubclass(field_info.annotation, ListDynamicallyReferenced)

def match_config_data_to_field_or_submodel(
        field_name: str,
        field_info: FieldInfo,
        parent_container: MutableMapping,
        root_config_data: MutableMapping = None,
        parents=None
):
    create_from_section_names = should_create_from_section_names(field_info)

    if inspect.isclass(field_info.annotation) and issubclass(field_info.annotation, DynamicallyReferenced):
        updated_value = match_config_data_to_field(
            field_name=field_name,
            field_info=field_info,
            field_value=parent_container[field_name],
            create_from_section_names=create_from_section_names,
            parent_container=parent_container,
            root_config_data=root_config_data,
            parents=parents
        )
        if isinstance(updated_value, list):
            updated_value = [{'ref': entry} for entry in updated_value]
        elif hasattr(updated_value, 'items'):  # dict
            updated_value = {key: {'ref': entry} for key, entry in updated_value.items()}
        else:  # str
            updated_value = {'ref': updated_value}
    elif hasattr(field_info.annotation, 'model_fields') and not create_from_section_names:
        # noinspection PyTypeChecker
        updated_value = match_config_data_to_model(
            model=field_info.annotation,
            config_data=parent_container[field_name],
            root_config_data=root_config_data,
            parents=parents
        )
    else:
        updated_value = match_config_data_to_field(
            field_name=field_name,
            field_info=field_info,
            field_value=parent_container[field_name],
            create_from_section_names=create_from_section_names,
            parent_container=parent_container,
            root_config_data=root_config_data,
            parents=parents
        )
    return updated_value


def walk_model(
        model: BaseModel,
        parents=None
):
    if parents is None:
        parents = []

    # Scan all model fields to look for values in the MutableMapping
    for field_name, field_info in model.model_fields.items():
        if inspect.isclass(field_info.annotation) and issubclass(field_info.annotation, DynamicallyReferenced):
            yield field_name, field_info, parents
        elif hasattr(field_info.annotation, 'model_fields'):
            yield from walk_model(
                model=field_info.annotation,
                parents=parents + [field_name]
            )
        else:
            yield field_name, field_info, parents
