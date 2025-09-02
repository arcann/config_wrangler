import os
import warnings
from typing import Optional

from pydantic import PrivateAttr, model_validator, Field

from config_wrangler.config_templates.config_hierarchy import ConfigHierarchy
from config_wrangler.config_templates.keepass_config import KeepassConfig
from config_wrangler.config_templates.password_defaults import PasswordDefaults
from config_wrangler.config_templates.password_source import PasswordSource, PasswordSourceValidated

__all__ = ['Credentials', 'PasswordDefaults', 'PasswordSource']

from config_wrangler.validate_config_hierarchy import config_hierarchy_validator


class Credentials(ConfigHierarchy):
    user_id: Optional[str] = None
    """
    The user ID to use
    """

    password_source: Optional[PasswordSourceValidated] = None
    """
    The source to use when getting a password for the user.  
    See :py:class:`PasswordSource` for valid values.
    """

    raw_password: Optional[str] = Field(repr=False, default=None)
    """
    This is only used for the extremely non-secure `CONFIG_FILE` password source.
    The password is stored directly in the config file next to the user_id with
    the setting name `raw_password`
    """

    keyring_section: Optional[str] = None
    """
    If the password_source is KEYRING, then which section (AKA system)
    should this module look for the password in.
    
    See https://pypi.org/project/keyring/
    or https://github.com/jaraco/keyring
    """
    keepass_config: Optional[str] = 'keepass'
    """
    If the password_source is KEEPASS, then which root level config item contains
    the settings for Keepass (must be an instance of 
    :py:class:`config_wrangler.config_templates.keepass_config.KeepassConfig`)
    """
    keepass: Optional[KeepassConfig] = None
    """
    If the password_source is KEEPASS, then load a sub-section with the 
    :py:class:`config_wrangler.config_templates.keepass_config.KeepassConfig`) settings
    """

    keepass_group: Optional[str] = None
    """
    If the password_source is KEEPASS, which group in the Keepass database should
    be searched for an entry with a matching entry.
    
    If is None, then the `KeepassConfig.default_group` value will be checked.
    If that is also None, then a ValueError will be raised.
    """

    keepass_title: Optional[str] = None
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
            raise ValueError(f"{self.full_item_name()} password_source is KEYRING but keyring_section is None")
        import keyring
        password = keyring.get_password(self.keyring_section, self.user_id)
        search_info = f"{self.keyring_section} {self.user_id}"
        return password, search_info

    def _get_password_config(self):
        warnings.warn(
            'Passwords stored directly in config or worse in code are not safe. Please make sure to fix this before deploying.',
            stacklevel=3,
        )
        password = self.raw_password
        search_info = f"{self.full_item_name()}.raw_password"
        return password, search_info

    @staticmethod
    def _get_envt_name(search_name: str) -> Optional[str]:
        if search_name in os.environ:
            return search_name
        else:
            search_name_upper = search_name.upper()
            for envt_var in os.environ:
                envt_var_upper = envt_var.upper()
                if envt_var_upper == search_name_upper:
                    return envt_var
            return None

    def _get_password_environment(self):
        password = self.raw_password
        if password is not None and password != '':
            # Env loader might have already found it for us. At least we'll assume that's where it came from.
            search_info = f"{self.full_item_name()}.raw_password"
            return password, search_info
        else:
            name_in_envt = self.full_item_name(delimiter='_').replace('.', '_')
            search_info_list = []
            password = None
            for envt_name_search in [
                f"PASSWORD_{self.user_id}",
                f"{self.user_id}_PASSWORD",
                self.user_id,
                f"{name_in_envt}_PASSWORD",
            ]:
                search_info_list.append(envt_name_search)
                envt_name_found = self._get_envt_name(envt_name_search)
                if envt_name_found is not None:
                    if envt_name_found in os.environ:
                        password = os.environ[envt_name_found]
                        break
            if password is None:
                raise ValueError(f"{self.full_item_name()} password_source = ENVIRONMENT. Value not found in {search_info_list}")
            else:
                return password, ','.join(search_info_list)

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

        try:
            if self.password_source == PasswordSource.KEYRING:
                password, search_info = self._get_password_keyring()
            elif self.password_source == PasswordSource.CONFIG_FILE:
                password, search_info = self._get_password_config()
            elif self.password_source == PasswordSource.ENVIRONMENT:
                password, search_info = self._get_password_environment()
            elif self.password_source == PasswordSource.KEEPASS:
                password, search_info = self._get_password_keepass()
            elif self.password_source == PasswordSource.AWS_ASSUME_ROLE:
                password = 'NOT A REAL PASSWORD'
                password_source = 'Assume Role'
            else:
                raise ValueError(f"invalid password_source")
        except Exception as e:
            raise ValueError(f"{self.full_item_name()} with password_source={self.password_source} got error {e}")

        if password is None or password == '':
            raise ValueError(f"{self.full_item_name()} password is not set. Source is {self.password_source} location = {search_info}")

        return password

    @model_validator(mode='after')
    def check_model(self):
        user_id = self.user_id
        if user_id == '' or user_id is None:
            if self.password_source != PasswordSource.AWS_ASSUME_ROLE:
                raise ValueError("user_id not provided")

        if self.password_source == PasswordSource.KEYRING:
            keyring_section = self.keyring_section
            if keyring_section is None:
                raise ValueError(f"{self.full_item_name()} password_source is KEYRING but keyring_section is None")
        elif self.password_source == PasswordSource.CONFIG_FILE:
            password = self.raw_password
            if password is None or password == '':
                raise ValueError(f"{self} password_source is Config but password is not set")
        return self

    @config_hierarchy_validator
    def _check_config_hierarchy(self):
        """
        Validator for checking that credentials are valid.
        The validation is performed if all of these are True:
        - validate_credentials is True or not set in the root model_config object.
        - validate_default is True or not set in the root model_config object.
        - validate_password_on_load is True (defaults to True) in this Credentials based object.
        """
        if self._root_config is None:
            raise ValueError("Credentials are not part of a ConfigRoot hierarchy")
        else:
            model_config = self._root_config.model_config
            validate_credentials = getattr(model_config, 'validate_credentials', True)
            if model_config.get('validate_default', True) and validate_credentials and self.validate_password_on_load:
                root_config = self._root_config.model_config
                root_validate_credentials = root_config.get('validate_credentials', True)
                if root_validate_credentials:
                    _ = self.get_password()
