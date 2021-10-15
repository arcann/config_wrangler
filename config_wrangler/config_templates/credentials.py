import logging
import typing
import warnings
from enum import auto

from pydantic import PrivateAttr, root_validator
from strenum import StrEnum

from config_wrangler.config_templates.config_hierarchy import ConfigHierarchy


class PasswordSource(StrEnum):
    CONFIG_FILE = auto()
    KEYRING = auto()
    KEEPASS = auto()


class Credentials(ConfigHierarchy):
    user_id: str
    password_source: PasswordSource = None
    raw_password: str = None
    keyring_section: str = 's3'
    keepass_config: str = 'keepass'
    keepass_group: str = None
    keepass_title: str = None
    validate_password_on_load: bool = True

    # Values to hide from config exports
    _private_value_atts = PrivateAttr(default={'raw_password'})

    def get_password(self) -> str:
        log = logging.getLogger(__name__)

        if self.password_source is None:
            try:
                passwords_defaults = getattr(self._root_config, 'passwords')
            except KeyError:
                raise ValueError(
                    f"{self.full_item_name()} password_source not provided and 'passwords' section not found"
                )
            try:
                self.password_source = passwords_defaults.password_source
            except AttributeError as e:
                raise ValueError(
                    f"{self.full_item_name()} password_source not provided "
                    f"and 'passwords' section does not have 'password_source' {e} "
                )

        if self.password_source == PasswordSource.KEYRING:
            if self.keyring_section is None:
                raise ValueError(f"{self.full_item_name()} keyring_section is None but password_source was keyring")
            import keyring
            password = keyring.get_password(self.keyring_section, self.user_id)
            search_info = f"{self.keyring_section} {self.user_id}"
        elif self.password_source == PasswordSource.CONFIG_FILE:
            warnings.warn(
                'Passwords stored directly in config or worse in code are not safe. Please make sure to fix this before deploying.'
            )
            password = self.raw_password
            search_info = ''
        elif self.password_source == PasswordSource.KEEPASS:
            try:
                keepass_config = getattr(self._root_config, self.keepass_config)
            except KeyError:
                raise ValueError(
                    f"{self.full_item_name()} keepass_config section {self.keepass_config} not found in config data"
                )
            try:
                get_password = keepass_config.get_password
            except AttributeError as e:
                raise ValueError(
                    f"{self.full_item_name()} keepass_config section {self.keepass_config} does not appear to be valid. "
                    f"{e}"
                )

            if self.keepass_group is None:
                if self.keyring_section is not None:
                    log.info(f"keepass_group not provided but keyring_section = {self.keyring_section}, using that for keepass group")
                    self.keepass_group = self.keyring_section
                else:
                    raise ValueError(
                        f"{self.full_item_name()} keepass_group not specified. "
                    )
            password = get_password(self.keepass_group, self.keepass_title, self.user_id)

        else:
            raise ValueError(f"{self.full_item_name()} invalid password_source {self.password_source}")

        if password is None or password == '':
            raise ValueError(f"{self.full_item_name()} password is not set. Source is {self.password_source} location = {search_info}")

        return password

    @root_validator
    def check_password(cls, values):
        if 'password_source' in values:
            if values['password_source'] is not None:
                values['password_source'] = values['password_source'].upper()

        user_id = values.get('user_id')
        if user_id == '' or user_id is None:
            if cls.__name__ == 'SQLAlchemyDatabase':
                if values.get('dialect') == 'sqlite':
                    # Bypass password checks
                    return values
            raise ValueError("user_id not provided")

        if values.get('password_source') == PasswordSource.KEYRING:
            keyring_section = values.get('keyring_section')
            if keyring_section is None:
                raise ValueError(f"{values} keyring_section is None but password_source was keyring")
        elif values.get('password_source') == PasswordSource.CONFIG_FILE:
            password = values.get('raw_password')
            if password is None or password == '':
                raise ValueError(f"{values} password_source is Config but password is not set")
        return values

    def _iter(
            self,
            to_dict: bool = False,
            by_alias: bool = False,
            include: typing.Union['AbstractSetIntStr', 'MappingIntStrAny'] = None,
            exclude: typing.Union['AbstractSetIntStr', 'MappingIntStrAny'] = None,
            exclude_unset: bool = False,
            exclude_defaults: bool = False,
            exclude_none: bool = False,
    ) -> 'TupleGenerator':
        """
        Iterate through the values, but hide any password (_private_value_atts)
        values in this output.  Passwords should be directly accessed by attribute name.
        """
        for key, value in super()._iter(
            to_dict=to_dict,
            by_alias=by_alias,
            include=include,
            exclude=exclude,
            exclude_unset=exclude_unset,
            exclude_defaults=exclude_defaults,
            exclude_none=exclude_none,
        ):
            if key in self._private_value_atts and value is not None:
                value = '*' * 8
            yield key, value


class PasswordDefaults(ConfigHierarchy):
    password_source: PasswordSource = None

    @root_validator
    def check_password(cls, values):
        if 'password_source' in values:
            if values['password_source'] is not None:
                values['password_source'] = values['password_source'].upper()
        return values
