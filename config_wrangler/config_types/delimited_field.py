from __future__ import annotations as _annotations

import typing
from typing import Any, Callable

from pydantic.fields import FieldInfo
from pydantic_core import PydanticUndefined

if typing.TYPE_CHECKING:
    from pydantic.fields import AliasPath, AliasChoices

class DelimitedListFieldInfo(FieldInfo):
    delimiter: str
    """
    The delimiter to use when parsing the value into a list. (DelimitedListFieldInfo specific) 
    """

    __slots__ = (
        'delimiter'
    )

    def __init__(self, delimiter: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self.delimiter = delimiter


# noinspection PyPep8Naming
def DelimitedListField(  # noqa: C901
        default: Any = PydanticUndefined,
        *,
        default_factory: Callable[[], Any] | None = PydanticUndefined,
        alias: str | None = PydanticUndefined,
        alias_priority: int | None = PydanticUndefined,
        validation_alias: str | AliasPath | AliasChoices | None = PydanticUndefined,
        serialization_alias: str | None = PydanticUndefined,
        title: str | None = PydanticUndefined,
        description: str | None = PydanticUndefined,
        examples: list[Any] | None = PydanticUndefined,
        exclude: bool | None = PydanticUndefined,
        include: bool | None = PydanticUndefined,
        discriminator: str | None = PydanticUndefined,
        json_schema_extra: dict[str, Any] | Callable[[dict[str, Any]], None] | None = PydanticUndefined,
        frozen: bool | None = PydanticUndefined,
        validate_default: bool | None = PydanticUndefined,
        repr: bool = PydanticUndefined,
        init_var: bool | None = PydanticUndefined,
        kw_only: bool | None = PydanticUndefined,
        pattern: str | None = PydanticUndefined,
        strict: bool | None = PydanticUndefined,
        gt: float | None = PydanticUndefined,
        ge: float | None = PydanticUndefined,
        lt: float | None = PydanticUndefined,
        le: float | None = PydanticUndefined,
        multiple_of: float | None = PydanticUndefined,
        allow_inf_nan: bool | None = PydanticUndefined,
        max_digits: int | None = PydanticUndefined,
        decimal_places: int | None = PydanticUndefined,
        min_length: int | None = PydanticUndefined,
        max_length: int | None = PydanticUndefined,
        delimiter: str = ','
) -> Any:
    """
    Create a field for a `list` of objects, plus other Pydantic `Field` configuration options.

    *Pydantic standard docs*:

    Used to provide extra information about a field, either for the model schema or complex validation. Some arguments
    apply only to number fields (`int`, `float`, `Decimal`) and some apply only to `str`.

    Args:
        default: Default value if the field is not set.
        default_factory: A callable to generate the default value, such as :func:`~datetime.utcnow`.
        alias: An alternative name for the attribute.
        alias_priority: Priority of the alias. This affects whether an alias generator is used.
        validation_alias: 'Whitelist' validation step. The field will be the single one allowed by the alias or set of
            aliases defined.
        serialization_alias: 'Blacklist' validation step. The vanilla field will be the single one of the alias' or set
            of aliases' fields and all the other fields will be ignored at serialization time.
        title: Human-readable title.
        description: Human-readable description.
        examples: Example values for this field.
        exclude: Whether to exclude the field from the model schema.
        include: Whether to include the field in the model schema.
        discriminator: Field name for discriminating the type in a tagged union.
        json_schema_extra: Any additional JSON schema data for the schema property.
        frozen: Whether the field is frozen.
        validate_default: Run validation that isn't only checking existence of defaults. `True` by default.
        repr: A boolean indicating whether to include the field in the `__repr__` output.
        init_var: Whether the field should be included in the constructor of the dataclass.
        kw_only: Whether the field should be a keyword-only argument in the constructor of the dataclass.
        strict: If `True`, strict validation is applied to the field.
            See [Strict Mode](../usage/strict_mode.md) for details.
        gt: Greater than. If set, value must be greater than this. Only applicable to numbers.
        ge: Greater than or equal. If set, value must be greater than or equal to this. Only applicable to numbers.
        lt: Less than. If set, value must be less than this. Only applicable to numbers.
        le: Less than or equal. If set, value must be less than or equal to this. Only applicable to numbers.
        multiple_of: Value must be a multiple of this. Only applicable to numbers.
        min_length: Minimum length for strings.
        max_length: Maximum length for strings.
        pattern: Pattern for strings.
        allow_inf_nan: Allow `inf`, `-inf`, `nan`. Only applicable to numbers.
        max_digits: Maximum number of allow digits for strings.
        decimal_places: Maximum number of decimal places allowed for numbers.
        delimiter: delimiter to use when parsing the input value

    Returns:
        A new [`FieldInfo`][pydantic.fields.FieldInfo], the return annotation is `Any` so `Field` can be used on
            type annotated fields without causing a typing error.
    """

    return DelimitedListFieldInfo.from_field(
        default,
        default_factory=default_factory,
        alias=alias,
        alias_priority=alias_priority,
        validation_alias=validation_alias,
        serialization_alias=serialization_alias,
        title=title,
        description=description,
        examples=examples,
        exclude=exclude,
        include=include,
        discriminator=discriminator,
        json_schema_extra=json_schema_extra,
        frozen=frozen,
        pattern=pattern,
        validate_default=validate_default,
        repr=repr,
        init_var=init_var,
        kw_only=kw_only,
        strict=strict,
        gt=gt,
        ge=ge,
        lt=lt,
        le=le,
        multiple_of=multiple_of,
        min_length=min_length,
        max_length=max_length,
        allow_inf_nan=allow_inf_nan,
        max_digits=max_digits,
        decimal_places=decimal_places,
        delimiter=delimiter,
    )
