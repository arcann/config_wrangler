from typing import *

from auto_all import public
from pydantic import PrivateAttr

from config_wrangler.config_templates.config_hierarchy import ConfigHierarchy
from config_wrangler.config_templates.password_source import PasswordSource, PasswordSourceValidated
from config_wrangler.config_types.path_types import PathFindUpExpandUser


@public
class KeepassConfig(ConfigHierarchy):
    user_id: str = 'KEEPASS'
    database_path: PathFindUpExpandUser
    default_group: Optional[str] = None
    password_source: PasswordSourceValidated = PasswordSource.KEYRING
    raw_password: Optional[str] = None
    keyring_section: Optional[str] = None
    keyring_user_id: Optional[str] = None
    alternate_group_names: Dict[str, str] = {}

    _db = PrivateAttr(default=None)
    _alternate_group_names_lower = PrivateAttr(default=None)
    _keepass_credentials = PrivateAttr(default=None)

    def open_database(self, force_refresh: bool = False) -> 'pykeepass.PyKeePass':
        if self._db is None or force_refresh:
            from pykeepass import PyKeePass

            credentials_args = dict(**self.__dict__)
            if self.password_source == PasswordSource.KEYRING:
                credentials_args['user_id'] = self.keyring_user_id
            else:
                credentials_args['user_id'] = 'KEEPASS'

            from config_wrangler.config_templates.credentials import Credentials
            self._keepass_credentials = Credentials(**credentials_args)
            self.add_child('_keepass_credentials', self._keepass_credentials)
            keepass_encryption_password = self._keepass_credentials.get_password()
            try:
                self._db = PyKeePass(self.database_path, password=keepass_encryption_password)
            except Exception as e:
                raise ValueError(f"PyKeePass error from {self.database_path}: {repr(e)}")

            self._alternate_group_names_lower = {k.lower(): v.lower() for k, v in self.alternate_group_names.items()}
        return self._db

    def get_group_contents(self, group: str) -> Iterable['pykeepass.entry.Entry']:
        kp = self.open_database()
        results = list()
        for group_object in kp.groups:
            if group_object.name is not None and group_object.name.lower() == group.lower():
                for entry in group_object.entries:
                    results.append(entry)
        return results

    def get_group_list_contents(self, group_list: Iterable[str]) -> Iterable['pykeepass.entry.Entry']:
        results = list()
        # Make a unique set of lower case group names
        group_set = {g.lower() for g in group_list}
        for group in group_set:
            results.extend(self.get_group_contents(group))
        return results

    @staticmethod
    def _get_entry_str_value(entry_value: Any) -> str:
        if entry_value is None:
            return ''
        else:
            return str(entry_value)

    def get_password(self, group: Optional[str], title: Optional[str], user_id: Optional[str]):
        if group is None:
            if self.default_group is not None:
                group = self.default_group
            else:
                raise ValueError(f"keepass_group not provided and keepass:default_group also not provided")
        group_lower = group.lower()
        group_search_set = {group_lower}
        if self._alternate_group_names_lower is not None:
            alt_group_lower = self._alternate_group_names_lower.get(group_lower)
            if alt_group_lower is not None:
                group_search_set.add(alt_group_lower)

        selectors = [f"group.lower in {group_search_set}"]
        if title is not None:
            selectors.append(f"Title.lower = '{title.lower()}'")
            title_lower = title.lower()
        else:
            title_lower = None

        if user_id is not None:
            selectors.append(f"User_name.lower = '{user_id.lower()}'")
            user_id_lower = user_id.lower()
        else:
            user_id_lower = None

        selectors_str = ' and '.join(selectors)
        entry_matches = list()
        for entry in self.get_group_list_contents(group_search_set):
            match = True
            if title is not None:
                if self._get_entry_str_value(entry.title).lower() != title_lower:
                    match = False
            if user_id is not None:
                if self._get_entry_str_value(entry.username).lower() != user_id_lower:
                    match = False
            if match:
                entry_matches.append(entry)
        if len(entry_matches) == 0:
            raise ValueError(f"Keepass does not have entry for {selectors_str} in {self.database_path}")
        elif len(entry_matches) > 1:
            selectors_str = ' and '.join(selectors)
            matches_description_parts = list()
            for entry in entry_matches:
                matches_description_parts.append(f"<group='{entry.group}' title='{entry.title}'/>")
            raise ValueError(
                f"Keepass has multiple matches for entry for {selectors_str} in {self.database_path}."
                f"{', '.join(matches_description_parts)}"
            )
        else:
            entry_password = entry_matches[0].password
            return entry_password
