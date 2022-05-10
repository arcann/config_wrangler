import ast
import inspect
import json
import logging
import re
import typing
from datetime import timezone, datetime

from pydantic import BaseModel
from pydantic.fields import SHAPE_LIST, SHAPE_SINGLETON, SHAPE_TUPLE, SHAPE_ITERABLE, SHAPE_SEQUENCE, \
    SHAPE_TUPLE_ELLIPSIS, SHAPE_SET, SHAPE_FROZENSET, SHAPE_DICT, SHAPE_DEFAULTDICT, Field, ModelField
from pydantic.utils import lenient_issubclass

from config_wrangler.config_exception import ConfigError
from config_wrangler.config_types.dynamically_referenced import DynamicallyReferenced


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
        for delimiter in ['\n', ',', '|']:
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


def inherit_fill(parent_config, child_config):
    for inherit_key, inherit_value in parent_config.items():
        if inherit_key not in child_config:
            child_config[inherit_key] = inherit_value


def find_referenced_section(
        field: ModelField,
        parents: typing.List[str],
        section_name: typing.Union[str, typing.MutableMapping],
        current_dict: typing.MutableMapping,
        root_dict: typing.MutableMapping
) -> typing.MutableMapping:
    inherit = field.field_info.extra.get('inherit', False)
    if isinstance(section_name, str):
        if section_name in root_dict:
            if inherit:
                inherit_fill(current_dict, root_dict[section_name])
            section_value = root_dict[section_name]
        elif section_name in current_dict:
            if inherit:
                inherit_fill(current_dict, current_dict[section_name])
            section_value = current_dict[section_name]
        else:
            raise ConfigError(
                f"{full_name(parents, field.alias)} refers to section {section_name} which does not exist."
            )
        return section_value
    else:
        return section_name


def match_config_data_to_field(
        field: ModelField,
        field_value: object,
        create_from_section_names: bool,
        parent_container: typing.MutableMapping,
        root_config_data: typing.MutableMapping,
        parents: typing.List[str],
):
    if field.shape == SHAPE_SINGLETON and field.type_ not in {list, tuple, dict, set, frozenset}:
        if create_from_section_names:
            if not hasattr(field.type_, '__fields__'):
                raise ValueError(f"{full_name(parents, field.alias)} has create_from_section_names but has no fields")
            section_value = find_referenced_section(
                field=field,
                parents=parents,
                section_name=field_value,
                current_dict=parent_container,
                root_dict=root_config_data,
            )
            section_value['config_source_name'] = field_value
            field_value = section_value
    elif (
        field.shape in {SHAPE_LIST, SHAPE_TUPLE, SHAPE_TUPLE_ELLIPSIS, SHAPE_ITERABLE, SHAPE_SEQUENCE}
        or (field.shape == SHAPE_SINGLETON and field.type_ in {list, tuple})
    ):
        if isinstance(field_value, str):
            field_value = parse_delimited_list(field, field_value)

        # Conditional change to field_value to obtain value from another config section
        if create_from_section_names:
            if not hasattr(field.type_, '__fields__'):
                raise ValueError(f"{full_name(parents, field.alias)} has create_from_section_names but has no fields")

            section_contents = list()
            for section_name in field_value:
                section_value = find_referenced_section(
                    field=field,
                    parents=parents,
                    section_name=section_name,
                    current_dict=parent_container,
                    root_dict=root_config_data,
                )
                if field.sub_fields:
                    # Transform section_value as needed
                    sub_field = field.sub_fields[0]
                    section_value = match_config_data_to_field_or_submodel(
                        field=sub_field,
                        parent_container={sub_field.alias: section_value},
                        root_config_data=root_config_data,
                        parents=parents + [field.alias, section_name]
                    )
                # Add name to the dict in case the model wants it
                section_value['config_source_name'] = section_name
                section_contents.append(section_value)
            field_value = section_contents
    elif (
            field.shape in {SHAPE_DICT, SHAPE_DEFAULTDICT}
            or (field.shape == SHAPE_SINGLETON and field.type_ in {dict})
    ):
        if isinstance(field_value, str):
            try:
                field_value = parse_as_literal_or_json(field_value)
            except ValueError as e:
                raise ConfigError(f"Field {full_name(parents, field.alias)} {e}")

        # Conditional change to field_value to obtain value from another config section
        if create_from_section_names:
            section_contents = dict()
            for key, value in field_value.items():
                if field.sub_fields:
                    sub_field = field.sub_fields[0]
                    sub_field.field_info.extra['create_from_section_names'] = True
                    # Transform section_value as needed
                    section_value = match_config_data_to_field(
                        field=sub_field,
                        field_value=value,
                        create_from_section_names=True,
                        parent_container=field_value,
                        root_config_data=root_config_data,
                        parents=parents + [field.alias, key, value]
                    )
                    section_contents[key] = section_value
                else:
                    section_value = find_referenced_section(
                        field=field,
                        parents=parents,
                        section_name=value,
                        current_dict=parent_container,
                        root_dict=root_config_data,
                    )
                    section_contents[key] = section_value
            field_value = section_contents
    elif (
            field.shape in {SHAPE_SET}
            or (field.shape == SHAPE_SINGLETON and field.type_ in {set})
    ):
        if isinstance(field_value, str):
            field_value = set(parse_delimited_list(field, field_value))
    elif (
            field.shape in {SHAPE_FROZENSET}
            or (field.shape == SHAPE_SINGLETON and field.type_ in {frozenset})
    ):
        if isinstance(field_value, str):
            field_value = frozenset(parse_delimited_list(field, field_value))
    # In all cases not explicitly matched above, we'll let pydantic parse it as is
    return field_value


def match_config_data_to_model(
        model: BaseModel,
        config_data: typing.MutableMapping,
        root_config_data: typing.MutableMapping = None,
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
                # Copy data into place where pydantic will expect it
                config_data[field.alias] = root_config_data[section_name]
            elif section_name_lower in root_config_name_map:
                found = True
                section_name = root_config_name_map[section_name_lower]
                # Copy data into place where pydantic will expect it
                config_data[field.alias] = root_config_data[section_name]

        if found:
            updated_value = match_config_data_to_field_or_submodel(
                field=field,
                parent_container=config_data,
                root_config_data=root_config_data,
                parents=parents + [field.alias]
            )
            config_data[field.alias] = updated_value
    return config_data


def match_config_data_to_field_or_submodel(
        field: ModelField,
        parent_container: typing.MutableMapping,
        root_config_data: typing.MutableMapping = None,
        parents=None
):
    create_from_section_names = field.field_info.extra.get('create_from_section_names', False)

    if inspect.isclass(field.type_) and issubclass(field.type_, DynamicallyReferenced):
        updated_value = match_config_data_to_field(
            field=field,
            field_value=parent_container[field.alias],
            create_from_section_names=create_from_section_names,
            parent_container=parent_container,
            root_config_data=root_config_data,
            parents=parents
        )
        if isinstance(updated_value, list):
            updated_value = [{'ref': entry} for entry in updated_value]
        else:  # Dict
            updated_value = {key: {'ref': entry} for key, entry in updated_value.items()}
    elif hasattr(field.type_, '__fields__') and not create_from_section_names:
        updated_value = match_config_data_to_model(
            model=field.type_,
            config_data=parent_container[field.alias],
            root_config_data=root_config_data,
            parents=parents
        )
    else:
        updated_value = match_config_data_to_field(
            field=field,
            field_value=parent_container[field.alias],
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
    for field in model.__fields__.values():
        if inspect.isclass(field.type_) and issubclass(field.type_, DynamicallyReferenced):
            yield field, parents
        elif hasattr(field.type_, '__fields__'):
            yield from walk_model(
                model=field.type_,
                parents=parents + [field.alias]
            )
        else:
            yield field, parents
