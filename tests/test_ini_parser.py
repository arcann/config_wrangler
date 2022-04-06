import inspect
import os
import typing
import unittest
from datetime import date, time, datetime
from unittest import mock

import pydantic
from pydantic import Field, AnyHttpUrl

from config_wrangler.config_from_ini_env import ConfigFromIniEnv
from config_wrangler.config_templates.config_hierarchy import ConfigHierarchy
from config_wrangler.config_templates.keepass_config import KeepassConfig
from config_wrangler.config_templates.sqlalchemy_database import SQLAlchemyDatabase


class TestSection(ConfigHierarchy):
    my_int: int
    my_float: float
    my_bool: bool
    my_str: str
    my_bytes: bytes
    my_list_auto_c: list
    my_list_auto_nl: list
    my_list_auto_pipe: list
    my_list_python: list
    my_list_json: list
    my_list_c: list = Field(delimiter=',')
    my_list_nl: list = Field(delimiter='\n')
    my_list_int_c: typing.List[int] = Field(delimiter=',')
    my_tuple_c: tuple = Field(delimiter=',')
    my_tuple_nl: tuple = Field(delimiter='\n')
    my_tuple_int_c: typing.Tuple[int, int, int] = Field(delimiter=',')
    my_dict: dict
    my_dict_str_int: typing.Dict[str, int]
    my_set: set
    my_set_int: typing.Set[int]
    my_frozenset: frozenset
    my_date: date
    my_time: time
    my_datetime: datetime
    my_url: AnyHttpUrl


class ConfigToTestWith(ConfigFromIniEnv):

    class Config:
        validate_all = True
        validate_assignment = True
        allow_mutation = True

    target_database: SQLAlchemyDatabase

    test_section: TestSection


class ConfigWithKeypass(ConfigToTestWith):
    keepass: KeepassConfig


class FakeKeepassConfig(ConfigHierarchy):
    database_path: str


class ConfigWithBadKeypass(ConfigToTestWith):
    keepass: FakeKeepassConfig


class TestIniParsee(unittest.TestCase):
    def setUp(self):
        self.test_files_path = self.get_test_files_path()

    def get_package_path(self):
        module_path = inspect.getfile(self.__class__)
        (tests_path, _) = os.path.split(module_path)
        return tests_path

    def get_test_files_path(self):
        return os.path.join(self.get_package_path(), 'test_config_files')

    def tearDown(self):
        pass

    def _test_simple_example_config(self, config):
        test_val = config.test_section.my_int
        self.assertEqual(test_val, 123)
        self.assertIsInstance(test_val, int)

        test_val = config.test_section.my_float
        self.assertAlmostEqual(test_val, 123.45)
        self.assertIsInstance(test_val, float)

        test_val = config.test_section.my_bool
        self.assertEqual(test_val, True)
        self.assertIsInstance(test_val, bool)

        test_val = config.test_section.my_list_auto_c
        self.assertEqual(test_val, ['a', 'b', 'c'])
        self.assertIsInstance(test_val, list)

        test_val = config.test_section.my_list_auto_nl
        self.assertEqual(test_val, ['a', 'b', 'c'])
        self.assertIsInstance(test_val, list)

        test_val = config.test_section.my_list_auto_pipe
        self.assertEqual(test_val, ['a', 'b', 'c'])
        self.assertIsInstance(test_val, list)

        test_val = config.test_section.my_list_c
        self.assertEqual(test_val, ['a', 'b', 'c'])
        self.assertIsInstance(test_val, list)

        test_val = config.test_section.my_list_python
        self.assertEqual(test_val, ['x', 'y', 'z'])
        self.assertIsInstance(test_val, list)

        test_val = config.test_section.my_list_json
        self.assertEqual(test_val, ["J", "S", "O", "N"])
        self.assertIsInstance(test_val, list)

        test_val = config.test_section.my_list_nl
        self.assertEqual(test_val, ['a', 'b', 'c'])
        self.assertIsInstance(test_val, list)

        test_val = config.test_section.my_list_int_c
        self.assertEqual(test_val, [1, 2, 3])
        self.assertIsInstance(test_val, list)
        self.assertIsInstance(test_val[0], int)

        test_val = config.test_section.my_tuple_c
        self.assertEqual(test_val, ('a1', 'b2', 'c3'))
        self.assertIsInstance(test_val, tuple)

        test_val = config.test_section.my_tuple_nl
        self.assertEqual(test_val, ('a1', 'b2', 'c3'))
        self.assertIsInstance(test_val, tuple)

        test_val = config.test_section.my_tuple_int_c
        self.assertEqual(test_val, (1, 2, 3))
        self.assertIsInstance(test_val, tuple)
        self.assertIsInstance(test_val[0], int)

        test_val = config.test_section.my_dict
        self.assertEqual(test_val, {1: 'One', 2: 'Two'})
        self.assertIsInstance(test_val, dict)

        test_val = config.test_section.my_dict_str_int
        self.assertEqual(test_val, {"one": 1, "two": 2})
        self.assertIsInstance(test_val, dict)
        self.assertEqual(test_val['one'], 1)
        self.assertIsInstance(test_val['one'], int)
        self.assertEqual(test_val['two'], 2)

        test_val = config.test_section.my_set
        self.assertEqual(test_val, {'A', 'B', 'C'})
        self.assertIsInstance(test_val, set)

        test_val = config.test_section.my_set_int
        self.assertEqual(test_val, {1, 2, 3})
        self.assertIsInstance(test_val, set)
        for set_val in test_val:
            self.assertIsInstance(set_val, int)

        test_val = config.test_section.my_frozenset
        self.assertEqual(test_val, frozenset({'A', 'B', 'C'}))
        self.assertIsInstance(test_val, frozenset)

        test_val = config.test_section.my_date
        self.assertEqual(test_val, date(year=2021, month=5, day=31))
        self.assertIsInstance(test_val, date)

        test_val = config.test_section.my_time
        self.assertEqual(test_val, time(hour=11, minute=55, second=23))
        self.assertIsInstance(test_val, time)

        test_val = config.test_section.my_datetime
        self.assertEqual(test_val, datetime(year=2021, month=5, day=31, hour=11, minute=23, second=53))
        self.assertIsInstance(test_val, datetime)

        test_val = config.test_section.my_url
        self.assertEqual(test_val, 'https://localhost:6553/')
        self.assertIsInstance(test_val, str)

    def test_read_start_path(self):
        config = ConfigToTestWith(
            file_name='simple_example.ini',
            start_path=self.get_test_files_path()
        )
        self._test_simple_example_config(config)

    def test_read_start_path_deeper_start(self):
        config = ConfigToTestWith(
            file_name='simple_example.ini',
            start_path=os.path.join(self.get_test_files_path(), 'deeper_dir')
        )
        self._test_simple_example_config(config)

    def test_read_start_path_deeper_start_2(self):
        config = ConfigToTestWith(
            file_name='simple_example.ini',
            start_path=os.path.join(self.get_test_files_path(), 'deeper_dir', 'deeper_does_not_exist')
        )
        self._test_simple_example_config(config)

    def test_read_cwd(self):
        with mock.patch("os.getcwd", return_value=self.get_test_files_path()) as mock_cwd:
            config = ConfigToTestWith(file_name='simple_example.ini')
            self._test_simple_example_config(config)
            mock_cwd.assert_called()

    def test_read_cwd_deeper_start(self):
        with mock.patch("os.getcwd", return_value=os.path.join(self.get_test_files_path(), 'deeper_dir')) as mock_cwd:
            config = ConfigToTestWith(file_name='simple_example.ini')
            self._test_simple_example_config(config)
            mock_cwd.assert_called()

    def test_does_not_exist(self):
        with self.assertRaises(FileNotFoundError):
            _ = ConfigToTestWith(file_name='simple_example.ini')

    def test_read_no_password(self):
        with self.assertRaises(pydantic.error_wrappers.ValidationError):
            _ = ConfigToTestWith(
                file_name='simple_example_no_pw.ini',
                start_path=os.path.join(self.get_test_files_path())
            )

    def test_read_keepass_good(self):
        try:
            from pykeepass import PyKeePass
        except ImportError:
            PyKeePass = None

        try:
            config = ConfigWithKeypass(
                file_name='simple_example_keepass_good.ini',
                start_path=os.path.join(self.get_test_files_path())
            )
            config.keepass.database_path = os.path.join(self.get_test_files_path(),  'keepass_db.kdbx')
            self.assertEqual(config.target_database.get_password(), 'b2g4VhNSKegFMtxo49Dz')

        except (ValueError, ImportError) as e:
            if "No module named 'pykeepass" in str(e):
                if PyKeePass is None:
                    self.skipTest(f"Test requires pykeepass")
                else:
                    raise "pykeepass imported by test but not by config_wrangler"
            else:
                raise

    def test_read_keepass_bad1(self):
        with self.assertRaises(ValueError) as raises_cm:
            _ = ConfigWithKeypass(
                file_name='simple_example_keepass_bad1.ini',
                start_path=os.path.join(self.get_test_files_path())
            )

    def test_read_keepass_bad2(self):
        with self.assertRaises(ValueError) as raises_cm:
            config = ConfigWithBadKeypass(
                file_name='simple_example_keepass_good.ini',
                start_path=os.path.join(self.get_test_files_path())
            )
            config.target_database.get_password()
        self.assertIn("'keepass' does not appear to be valid",
                      str(raises_cm.exception)
                      )

    def test_read_keepass_bad_group(self):
        try:
            from pykeepass import PyKeePass

            config = ConfigWithKeypass(
                file_name='simple_example_keepass_good.ini',
                start_path=os.path.join(self.get_test_files_path())
            )
            config.keepass.database_path = os.path.join(self.get_test_files_path(), 'keepass_db.kdbx')

            config.target_database.keepass_group = 'bad'
            with self.assertRaises(ValueError) as raised:
                config.target_database.get_password()
            self.assertIn("group 'bad'", str(raised.exception))
            self.assertIn("not found", str(raised.exception))

        except ImportError:
            self.skipTest(f"Test requires pykeepass")

    def test_read_keepass_bad_userid(self):
        try:
            from pykeepass import PyKeePass

            config = ConfigWithKeypass(
                file_name='simple_example_keepass_good.ini',
                start_path=os.path.join(self.get_test_files_path())
            )
            config.keepass.database_path = os.path.join(self.get_test_files_path(), 'keepass_db.kdbx')

            config.target_database.user_id = 'bad'
            with self.assertRaises(ValueError) as raised:
                config.target_database.get_password()
            self.assertIn("does not have entry for", str(raised.exception))
            self.assertIn("'bad'", str(raised.exception))

        except ImportError:
            self.skipTest(f"Test requires pykeepass")

    def test_read_keyring_good(self):
        try:
            import keyring
        except ImportError:
            keyring = None

        try:
            password = 'mysuperpassword'
            if keyring is not None:
                # If keyring is actually installed, use it to set the password
                keyring.set_password('s3', 'python_unittester_01', password)
            config = ConfigToTestWith(
                file_name='simple_example_keyring.ini',
                start_path=os.path.join(self.get_test_files_path())
            )
            self.assertEqual(config.target_database.get_password(), password)
        except (ValueError, ImportError) as e:
            if "No module named 'keyring'" in str(e):
                if keyring is None:
                    self.skipTest(f"Test requires keyring")
                else:
                    raise "keyring imported by test but not by config_wrangler"
            else:
                raise
