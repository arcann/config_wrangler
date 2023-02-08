import warnings
from typing import *

import pydantic.typing
from pydantic import PrivateAttr, root_validator

from config_wrangler.config_templates.config_hierarchy import ConfigHierarchy
from config_wrangler.config_templates.keepass_config import KeepassConfig
from config_wrangler.config_templates.password_defaults import PasswordDefaults
from config_wrangler.config_templates.password_source import PasswordSource
from config_wrangler.config_types.dynamically_referenced import DynamicallyReferenced

__all__ = ['Credentials', 'PasswordDefaults', 'PasswordSource']


class Credentials(ConfigHierarchy):
    user_id: str
    """
    The user ID to use
    """

    password_source: PasswordSource = None
    """
    The source to use when getting a password for the user.  
    See :py:class:`PasswordSource` for valid values.
    """

    raw_password: str = None
    """
    This is only used for the extremely non-secure `CONFIG_FILE` password source.
    The password is stored directly in the config file next to the user_id with
    the setting name `raw_password`
    """

    keyring_section: str = None
    """
    If the password_source is KEYRING, then which section (AKA system)
    should this module look for the password in.
    
    See https://pypi.org/project/keyring/
    or https://github.com/jaraco/keyring
    """
    keepass_config: str = 'keepass'
    """
    If the password_source is KEEPASS, then which root level config item contains
    the settings for Keepass (must be an instance of 
    :py:class:`config_wrangler.config_templates.keepass_config.KeepassConfig`)
    """
    keepass: KeepassConfig = None
    """
    If the password_source is KEEPASS, then load a sub-section with the 
    :py:class:`config_wrangler.config_templates.keepass_config.KeepassConfig`) settings
    """

    keepass_group: str = None
    """
    If the password_source is KEEPASS, which group in the Keepass database should
    be searched for an entry with a matching entry.
    
    If is None, then the `KeepassConfig.default_group` value will be checked.
    If that is also None, then a ValueError will be raised.
    """

    keepass_title: str = None
    """
    If the password_source is KEEPASS, this is an optional filter on the title
    of the keepass entries in the group.
    """

    validate_password_on_load: bool = True
    """
    Should config_wrangler query the password source for this password at 
    load (startup) time? If so, it will raise an error if the password is 
    None or an empty string. It **does not** actually connect or 
    authenticate the user_id & password combination.
    """

    # Values to hide from config exports
    _private_value_atts = PrivateAttr(default={'raw_password'})

    def _get_password_keyring(self):
        if self.keyring_section is None:
            raise ValueError(f"{self.full_item_name()} keyring_section is None but password_source was keyring")
        import keyring
        password = keyring.get_password(self.keyring_section, self.user_id)
        search_info = f"{self.keyring_section} {self.user_id}"
        return password, search_info

    def _get_password_config(self):
        warnings.warn(
            'Passwords stored directly in config or worse in code are not safe. Please make sure to fix this before deploying.'
        )
        password = self.raw_password
        search_info = f"{self.full_item_name()}.raw_password"
        return password, search_info

    def _get_keepass_config_str_ref(self) -> KeepassConfig:
        # Try older keepass_config string reference
        keepass_config = None
        if self.keepass_config is not None:
            try:
                if self._root_config is None:
                    raise ValueError("get_password called on Credentials that are not part of a ConfigRoot hierarchy (and keepass_config used)")
                keepass_config = getattr(self._root_config, self.keepass_config)
                if not isinstance(keepass_config, KeepassConfig):
                    raise ValueError(f"{self.full_item_name()} keepass_config is {type(keepass_config)} = {keepass_config} not KeepassConfig instance")
            except (KeyError, AttributeError):
                pass
        return keepass_config

    def _get_keepass_config_sub_section(self) -> KeepassConfig:
        if self.keepass is not None:
            keepass_config = self.keepass
        else:
            # Try root passwords subsection definition
            if self._root_config is None:
                raise ValueError(
                    "get_password called on Credentials that are not part of a ConfigRoot hierarchy "
                    "and does not have a local keepass_config or keepass sub-section"
                )
            if self._root_config.passwords is None:
                raise ValueError(
                    f"{self.full_item_name()} get_password called with PasswordSource = KEEPASS, "
                    f"but keepass_config/keepass is not in "
                    f"local section and yet the root passwords section is missing."
                )
            if self._root_config.passwords.keepass is None:
                raise ValueError(
                    f"{self.full_item_name()} get_password called with PasswordSource = KEEPASS, but keepass_config/keepass is not in "
                    f"local section and yet the root passwords section is also missing keepass_config."
                )
            keepass_config = self._root_config.passwords.keepass

        if not isinstance(keepass_config, KeepassConfig):
            raise ValueError(f"{self.full_item_name()} keepass_config is {type(keepass_config)} = {keepass_config} not KeepassConfig instance")

        return keepass_config

    def _get_password_keepass(self):
        keepass_config = self._get_keepass_config_str_ref()
        if keepass_config is None:
            keepass_config = self._get_keepass_config_sub_section()

        try:
            search_info = keepass_config.full_item_name()
            get_password = keepass_config.get_password
            try:
                password = get_password(self.keepass_group, self.keepass_title, self.user_id)
            except ValueError as e:
                raise ValueError(f"{self.full_item_name()} -> keepass config {keepass_config.full_item_name()} error {e}")
        except AttributeError as e:
            raise ValueError(
                f"{self.full_item_name()} -> keepass config {keepass_config.full_item_name()} does not appear to be valid. "
                f"{e}"
            )

        return password, search_info

    def get_password(self) -> str:
        """
        Get the password for this resource.
        `password_source` controls where it looks for the password.
        If that is None, then the root level `passwords` container is checked for `password_source` value.
        """
        if self.password_source is None:
            if self._root_config is None:
                raise ValueError("get_password called on Credentials that are not part of a ConfigRoot hierarchy")
            try:
                passwords_defaults = getattr(self._root_config, 'passwords')
            except AttributeError:
                raise ValueError(
                    f"{self.full_item_name()} password_source not provided and 'passwords' section not found"
                )
            if passwords_defaults is None:
                raise ValueError(
                    f"{self.full_item_name()} password_source not provided "
                    f"and 'passwords' section does not exist."
                )
            else:
                try:
                    self.password_source = passwords_defaults.password_source
                except AttributeError as e:
                    raise ValueError(
                        f"{self.full_item_name()} password_source not provided "
                        f"and 'passwords' section does not have 'password_source' {e} "
                    )

        if self.password_source == PasswordSource.KEYRING:
            password, search_info = self._get_password_keyring()
        elif self.password_source == PasswordSource.CONFIG_FILE:
            password, search_info = self._get_password_config()
        elif self.password_source == PasswordSource.KEEPASS:
            password, search_info = self._get_password_keepass()
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

    def _validate_model_password(self):
        if self._root_config is None:
            raise ValueError("_validate_model_password called on Credentials that are not part of a ConfigRoot hierarchy")
        if self._root_config.Config.validate_all and self.validate_password_on_load:
            config = self._root_config.Config
            validate_passwords = getattr(config, 'validate_passwords', True)
            if validate_passwords:
                _ = self.get_password()

    def _iter(
            self,
            to_dict: bool = False,
            by_alias: bool = False,
            include: Union['pydantic.typing.AbstractSetIntStr', 'pydantic.typing.MappingIntStrAny'] = None,
            exclude: Union['pydantic.typing.AbstractSetIntStr', 'pydantic.typing.MappingIntStrAny'] = None,
            exclude_unset: bool = False,
            exclude_defaults: bool = False,
            exclude_none: bool = False,
    ) -> 'pydantic.typing.TupleGenerator':
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
