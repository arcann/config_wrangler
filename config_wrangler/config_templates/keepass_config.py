import typing

from pydantic import PrivateAttr, root_validator

from config_wrangler.config_types.path_types import PathExpandUser
from config_wrangler.config_templates.config_hierarchy import ConfigHierarchy
from config_wrangler.config_templates.credentials import Credentials, PasswordSource


class KeepassConfig(ConfigHierarchy):
    database_path: PathExpandUser
    password_source: PasswordSource = PasswordSource.KEYRING
    raw_password: str = None
    keyring_section: str = 's3'
    keyring_user_id: str = None
    alternate_group_names: typing.Dict[str, str] = {}

    _db = PrivateAttr(default=None)
    _alternate_group_names_lower = PrivateAttr(default=None)
    _keepass_credentials = PrivateAttr(default=None)

    @root_validator
    def check_password(cls, values):
        if 'password_source' in values:
            if values['password_source'] is not None:
                values['password_source'] = values['password_source'].upper()
        return values

    def open_database(self) -> 'pykeepass.PyKeePass':
        if self._db is None:
            from pykeepass import PyKeePass

            credentials_args = dict(**self.__dict__)
            if self.password_source == PasswordSource.KEYRING:
                credentials_args['user_id'] = self.keyring_user_id
            else:
                credentials_args['user_id'] = 'not-real-userid_config-file'

            self._keepass_credentials = Credentials(**credentials_args)
            self.set_as_child('_keepass_credentials', self._keepass_credentials)
            keepass_encryption_password = self._keepass_credentials.get_password()
            try:
                self._db = PyKeePass(self.database_path, password=keepass_encryption_password)
            except Exception as e:
                raise ValueError(f"PyKeePass error from {self.database_path}: {repr(e)}")

            self._alternate_group_names_lower = {k.lower(): v.lower() for k, v in self.alternate_group_names.items()}
        return self._db

    def get_password(self, group: str, title: str, user_id: str):
        kp = self.open_database()

        group_matches = list()
        group_lower = group.lower()
        group_search_set = {group_lower}
        alt_group_lower = self._alternate_group_names_lower.get(group_lower)
        if alt_group_lower is not None:
            group_search_set.add(alt_group_lower)

        for group_object in kp.groups:
            if group_object.name is not None and group_object.name.lower() in group_search_set:
                group_matches.append(group_object)
        if len(group_matches) == 0:
            raise ValueError(f"Keepass group '{group}' not found in {self.database_path}")
        elif len(group_matches) > 1:
            raise ValueError(
                f"Keepass group '{group}' multiple matches in {self.database_path}.  group_matches: {group_matches}"
            )
        else:
            group_object = group_matches[0]
            selectors = []
            if title is not None:
                selectors.append(f"Title = '{title}'")
                title_lower = title.lower()
            else:
                title_lower = None

            if user_id is not None:
                selectors.append(f"User_name = '{user_id}'")
                user_id_lower = user_id.lower()
            else:
                user_id_lower = None

            selectors_str = ' and '.join(selectors)
            entry_matches = list()
            for entry in group_object.entries:
                match = True
                if title is not None:
                    if entry.title is not None and entry.title.lower() == title_lower:
                        match = True
                    else:
                        match = False
                if user_id is not None:
                    if entry.username is not None and entry.username.lower() == user_id_lower:
                        match = True
                    else:
                        match = False
                if match:
                    entry_matches.append(entry.password)
            if len(entry_matches) == 0:
                raise ValueError(f"Keepass group '{group_object.name}' does not have entry for {selectors_str} in {self.database_path}")
            elif len(entry_matches) > 1:
                selectors_str = ' and '.join(selectors)
                raise ValueError(
                    f"Keepass group '{group_object.name}' multiple matches for entry for {selectors_str} in {self.database_path}"
                )
            else:
                entry_password = entry_matches[0]
                return entry_password
