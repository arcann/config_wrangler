import ast
import json
import logging
import re
import types
import warnings
from datetime import timezone, datetime
from enum import Enum, auto
from typing import *

from pydantic import BaseModel, ValidationError
from pydantic.fields import FieldInfo
from pydicti import dicti, Dicti

from config_wrangler.config_exception import ConfigError
from config_wrangler.config_types.delimited_field import DelimitedListFieldInfo
from config_wrangler.config_types.dynamically_referenced import DynamicallyReferenced, DynamicFieldInfo


# Moved here because  Pydantic V2 deprecated it
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
                    for union_cls in get_args(cls):
                        if lenient_issubclass(union_cls, class_or_tuple):
                            return True
                    return False
                else:
                    return issubclass(origin, class_or_tuple)

    except TypeError:
        if isinstance(cls, (types.GenericAlias, types.UnionType)):
            return False
        raise


def get_inner_type(cls: Any):
    try:
        origin = cls.__origin__
    except AttributeError:
        origin = get_origin(cls)

    if origin == Union:
        for inner_cls in get_args(cls):
            return get_inner_type(inner_cls)
    else:
        return get_args(cls)


def has_sub_fields(inner_type: Type):
    return hasattr(inner_type, 'model_fields')


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

def interpolate_value(*, value: str, container: MutableMapping, root_config_data: MutableMapping) -> str:
    """
    Throws: ValueError if value can not be interpolated
    """
    if '$' not in value:
        return value
    else:
        depth = 0
        done = False
        new_value = value
        while not done:
            done = True
            depth += 1
            variables_cnt = 0
            result_values = []
            next_start = 0
            if isinstance(new_value, str):
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
                        except ValueError as e1:
                            try:
                                variable_replacement = resolve_variable(
                                    container,
                                    variable_name,
                                    part_delimiter=part_delimiter,
                                )
                            except ValueError as e2:
                                ValueError(f"<<{e1} resolving {variable_name}>>")
                    else:
                        try:
                            # Search in the local container instead of the root
                            # Change to case-insensitive dict
                            search_container = Dicti(container)
                            variable_replacement = search_container[variable_name]
                        except KeyError:
                            raise ValueError(f"<<{variable_name} NOT FOUND>>",)

                    result_values.append(new_value[next_start:var_start])
                    result_values.append(variable_replacement)
                    next_start = var_end
                if variables_cnt > 0:
                    if next_start < len(new_value):
                        result_values.append(new_value[next_start:])
                    result_values = [part for part in result_values if part != '']
                    if len(result_values) == 1:
                        # Possibly not a string -- maybe a dict
                        new_value = result_values[0]
                        if not isinstance(new_value, str):
                            done = True
                    else:
                        new_value = ''.join([str(v) for v in result_values])

                    if depth < 50:
                        done = False
                    else:
                        raise ValueError(
                            f"Interpolation recursion depth limit reached on value {value} "
                            f"ended processing with {new_value}"
                        )
        return new_value

class ContainerType(Enum):
    Mapping = auto()
    List = auto()
    Tuple = auto()
    Model = auto()

def set_container_value(
        container_type: ContainerType,
        container: Union[MutableMapping,List,BaseModel],
        attr: Union[str, int],
        value: Any
):
    if container_type == ContainerType.Mapping:
        container[attr] = value
    elif container_type == ContainerType.List:
        container[attr] = value
    elif container_type == ContainerType.Tuple:
        raise ValueError(
            f"Can't interpolate {value} inside tuple. Make it a list! See {breadcrumbs}"
        )
    else: # Model
        setattr(container, attr, value)

def interpolate_values(
        container: Union[MutableMapping,List,BaseModel],
        root_config_data: MutableMapping,
        breadcrumbs: List[str] = None,
) -> List[Tuple[str, str]]:
    errors = []
    if breadcrumbs is None:
        breadcrumbs = []
    if isinstance(container, MutableMapping):
        container_type = ContainerType.Mapping
        value_tuples = container.items()
    elif isinstance(container, list):
        container_type = ContainerType.List
        value_tuples = list(enumerate(container))
    elif isinstance(container, tuple):
        # We can't update the tuple so interpolation won't work
        # Howver, caller should change it to a list
        raise ValueError(
            f"Can't interpolate {value} inside tuple to {new_value}. Make it a list! See {breadcrumbs}"
        )
    else:
        container_type = ContainerType.Model
        value_tuples = list(container)

    for attr, value in value_tuples:
        if isinstance(value, MutableMapping) or isinstance(value, BaseModel) or isinstance(value, list) or isinstance(value, tuple):
            if isinstance(value, tuple):
                warnings.warn(f"Value of {attr} changed from tuple to list")
                # Convert to a list
                value = list(value)
                set_container_value(
                    container_type=container_type,
                    container=container,
                    attr=attr,
                    value=value,
                )
            sub_errors = interpolate_values(container=value, root_config_data=root_config_data, breadcrumbs=breadcrumbs + [attr])
            errors.extend(sub_errors)
        elif isinstance(value, str):
            try:
                new_value = interpolate_value(value=value, container=container, root_config_data=root_config_data)
                if new_value != value:
                    set_container_value(
                        container_type=container_type,
                        container=container,
                        value=new_value,
                        attr=attr,
                    )
            except ValueError as e:
                errors.append(('.'.join(breadcrumbs), str(e)))
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
            # Single value list
            result = [value]
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
                parts_used.append((*parents, section_name_2,))
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


def build_referenced_objects(
    field_name: str,
    field_info: FieldInfo,
    parents: List[str],
    parent_container: MutableMapping,
    root_config_data: MutableMapping,
    list_of_sections: Sequence[str],
    inner_type: type[BaseModel],
) -> Dict[str, BaseModel]:
    section_name = None
    try:
        section_contents = dict()
        for section_name in list_of_sections:
            # For DynamicallyReferenced we don't use the full value returned
            # here, but this helps us by validating the reference
            ref_section_value = find_referenced_section(
                field_name=field_name,
                field_info=field_info,
                parents=parents,
                section_name=section_name,
                current_dict=parent_container,
                root_dict=root_config_data,
            )
            if issubclass(inner_type, DynamicallyReferenced):
                # In the case of DynamicallyReferenced it refers to an existing static instance,
                # so we don't build a new instance, we instead just store the pointer.
                inner_type_instance = DynamicallyReferenced(ref=section_name)
            else:
                inner_type_instance = inner_type(**ref_section_value)
            section_contents[section_name] = inner_type_instance
        return section_contents
    except ValidationError as e:
        raise ValueError(f"Field {full_name(parents, field_name)} error on section {section_name} = {repr(e)})")


def match_config_data_to_field(
        field_name: str,
        field_info: FieldInfo,
        field_value: object,
        parent_container: MutableMapping,
        root_config_data: MutableMapping,
        parents: List[str],
):
    if lenient_issubclass(field_info.annotation, (str, int, float)):
        pass
    elif lenient_issubclass(field_info.annotation, list):
        if isinstance(field_value, str):
            field_value = parse_delimited_list(field_name, field_info, field_value)

        inner_type_args = get_inner_type(field_info.annotation)
        if len(inner_type_args) > 1:
            raise SyntaxError(
                f"{full_name(parents, field_name)} has type {field_info.annotation} "
                f"with more than one inner type {inner_type_args}"
            )
        elif len(inner_type_args) == 1:
            inner_type = inner_type_args[0]
            if has_sub_fields(inner_type):
                ref_object_dict = build_referenced_objects(
                    field_name=field_name,
                    field_info=field_info,
                    parents=parents,
                    parent_container=parent_container,
                    root_config_data=root_config_data,
                    list_of_sections=field_value,
                    inner_type=inner_type,
                )
                field_value = list(ref_object_dict.values())
    elif lenient_issubclass(field_info.annotation, tuple):
        if isinstance(field_value, str):
            field_value = parse_delimited_list(field_name, field_info, field_value)

        # See docs for Tuple annotations
        # https://docs.python.org/3/library/typing.html#annotating-tuples
        inner_type_args = get_inner_type(field_info.annotation)
        if len(inner_type_args) == 0:
            # Nothing to do for untyped tuple container
            pass
        elif len(inner_type_args) == 2 and inner_type_args[1] == Ellipsis:
            inner_type = inner_type_args[0]
            if has_sub_fields(inner_type):
                ref_object_dict = build_referenced_objects(
                    field_name=field_name,
                    field_info=field_info,
                    parents=parents,
                    parent_container=parent_container,
                    root_config_data=root_config_data,
                    list_of_sections=field_value,
                    inner_type=inner_type,
                )
                field_value = list(ref_object_dict.values())
        elif len(inner_type_args) != len(field_value):
            raise ValueError(
                f"{full_name(parents, field_name)} has type {field_info.annotation} "
                f"expects {len(inner_type_args)} values but got {len(field_value)} values."
            )
        else:
            new_field_values = list()
            for inner_type, value in zip(inner_type_args, field_value):
                if has_sub_fields(inner_type):
                    ref_object_dict = build_referenced_objects(
                        field_name=field_name,
                        field_info=field_info,
                        parents=parents,
                        parent_container=parent_container,
                        root_config_data=root_config_data,
                        list_of_sections=[value],
                        inner_type=inner_type,
                    )
                    new_field_values.append(ref_object_dict[value])
                else:
                    new_field_values.append(value)
    elif lenient_issubclass(field_info.annotation, dict):
        if isinstance(field_value, str):
            try:
                field_value = parse_as_literal_or_json(field_value)
            except ValueError as e:
                try:
                    list_of_sections = parse_delimited_list(field_name, field_info, field_value)
                    inner_type_args = get_inner_type(field_info.annotation)
                    if len(inner_type_args) != 2:
                        raise SyntaxError(
                            f"{full_name(parents, field_name)} has type {field_info.annotation} "
                            f"without exactly 2 inner types {inner_type_args}"
                        )
                    elif len(inner_type_args) == 2:
                        inner_type1 = inner_type_args[0]
                        if inner_type1 != str:
                            raise SyntaxError(
                                f"{full_name(parents, field_name)} has type {field_info.annotation} "
                                f"with the first inner type not being str (it is {inner_type1})"
                            )
                        inner_type2 = inner_type_args[1]
                        if has_sub_fields(inner_type2):
                            ref_object_dict = build_referenced_objects(
                                field_name=field_name,
                                field_info=field_info,
                                parents=parents,
                                parent_container=parent_container,
                                root_config_data=root_config_data,
                                list_of_sections=list_of_sections,
                                inner_type=inner_type2,
                            )
                            field_value = ref_object_dict
                except ValueError as e2:
                    raise ConfigError(
                        f"Field {full_name(parents, field_name)}"
                        f"Tried as list of section references and got error {e2}.\n"
                        f"Also tried as literal and got {e}"
                    )
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

        if field_lower in config_name_map:
            found = True
            source_field_name = config_name_map[field_lower]
            if source_field_name != field_name:
                config_data[field_name] = config_data[source_field_name]
                del config_data[source_field_name]
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


def match_config_data_to_field_or_submodel(
        field_name: str,
        field_info: FieldInfo,
        parent_container: MutableMapping,
        root_config_data: MutableMapping = None,
        parents=None
):

    if has_sub_fields(field_info.annotation):
        if field_name not in parent_container:
            raise ValueError(f"Field {full_name(parents, field_name)} not found.")

        if isinstance(field_info, DynamicFieldInfo):
            ref_object_dict = build_referenced_objects(
                field_name=field_name,
                field_info=field_info,
                parents=parents,
                parent_container=parent_container,
                root_config_data=root_config_data,
                list_of_sections=[parent_container[field_name]],
                inner_type=field_info.annotation,
            )
            if lenient_issubclass(field_info.annotation, BaseModel):
                updated_value = list(ref_object_dict.values())[0]
            elif lenient_issubclass(field_info.annotation, list):
                updated_value = list(ref_object_dict.values())
            elif lenient_issubclass(field_info.annotation, set):
                updated_value = set(ref_object_dict.values())
            elif lenient_issubclass(field_info.annotation, frozenset):
                updated_value = frozenset(ref_object_dict.values())
            elif lenient_issubclass(field_info.annotation, dict):
                updated_value = ref_object_dict
            else:
                raise ValueError(
                    f"Field {full_name(parents, field_name)} "
                    f"DynamicFieldInfo type {field_info.annotation} not expected"
                )
        else:
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
        if has_sub_fields(field_info.annotation):
            # noinspection PyTypeChecker
            yield from walk_model(
                model=field_info.annotation,
                parents=parents + [field_name]
            )
        else:
            yield field_name, field_info, parents
