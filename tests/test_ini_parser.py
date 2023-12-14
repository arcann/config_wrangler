import os
import unittest
import warnings
from datetime import date, time, datetime
from typing import *
from unittest import mock

import pydantic
from pydantic import Field, AnyHttpUrl, DirectoryPath
from pydantic_core import Url

from config_wrangler.config_from_ini_env import ConfigFromIniEnv
from config_wrangler.config_root import ConfigRoot
from config_wrangler.config_templates.config_hierarchy import ConfigHierarchy
from config_wrangler.config_templates.credentials import Credentials
from config_wrangler.config_templates.keepass_config import KeepassConfig
from config_wrangler.config_templates.sqlalchemy_database import SQLAlchemyDatabase
from config_wrangler.config_types.delimited_field import DelimitedListField
from config_wrangler.config_wrangler_config import ConfigWranglerConfig
from tests.base_tests_mixin import Base_Tests_Mixin


class Environment(ConfigHierarchy):
    name: str = Field(..., env='env_name')
    # Path types are not used for test since we don't want to need specific path to exists
    temp_data_dir: str
    source_data_dir: str


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
    my_list_c: Optional[List[str]] = DelimitedListField(delimiter=',')
    my_list_nl: Union[List[str], None] = DelimitedListField(delimiter='\n')
    my_list_int_c: List[int] = DelimitedListField(delimiter=',')
    my_tuple_c: tuple = DelimitedListField(delimiter=',')
    my_tuple_nl: tuple = DelimitedListField(delimiter='\n')
    my_tuple_int_c: Tuple[int, int, int] = DelimitedListField(delimiter=',')
    my_dict: dict
    my_dict_str_int: Dict[str, int]
    my_set: set
    my_set_int: Set[int]
    my_frozenset: frozenset
    my_date: date
    my_time: time
    my_datetime: datetime
    my_url: AnyHttpUrl
    double_interpolate: str
    triple_interpolate: str
    a: str
    b: str
    c: str
    my_environment: Environment


class ConfigToTestWith(ConfigFromIniEnv):

    model_config = ConfigWranglerConfig(
        validate_default=True,
        validate_assignment=True,
        validate_credentials=True,
    )

    target_database: SQLAlchemyDatabase

    test_section: TestSection


class TestSettings(ConfigHierarchy):
    config_files_path: DirectoryPath


class ConfigWithTestFilePath(ConfigToTestWith):
    test_settings: TestSettings


class ConfigWithKeypass(ConfigWithTestFilePath):
    keepass: KeepassConfig


class FakeKeepassConfig(ConfigHierarchy):
    pass


class ConfigWithBadKeypass(ConfigToTestWith):
    keepass: FakeKeepassConfig


class TestIniParser(unittest.TestCase, Base_Tests_Mixin):
    def setUp(self):
        self.test_files_path = self.get_test_files_path()

    def tearDown(self):
        try:
            del os.environ['test_settings_config_files_path']
        except KeyError:
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
        self.assertEqual(test_val, {1: 'One', 2: 'Two'}, f"my_dict got {test_val} expected {{1: 'One', 2: 'Two'}}")
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
        self.assertEqual(test_val, Url('https://localhost:6553/'))
        self.assertIsInstance(test_val, Url)

        self.assertEqual(config.test_section.double_interpolate, 'My DB is in ./example_db')

        self.assertEqual(config.test_section.triple_interpolate, '--**++C++**--')

    def test_read_start_path(self):
        config = ConfigToTestWith(
            file_name='test_good.ini',
            start_path=self.get_test_files_path()
        )
        self._test_simple_example_config(config)

    def test_read_start_path_deeper_start(self):
        config = ConfigToTestWith(
            file_name='test_good.ini',
            start_path=os.path.join(self.get_test_files_path(), 'deeper_dir')
        )
        self._test_simple_example_config(config)

    def test_read_start_path_deeper_start_2(self):
        config = ConfigToTestWith(
            file_name='test_good.ini',
            start_path=os.path.join(self.get_test_files_path(), 'deeper_dir', 'deeper_does_not_exist')
        )
        self._test_simple_example_config(config)

    def test_read_cwd(self):
        with mock.patch("os.getcwd", return_value=self.get_test_files_path()) as mock_cwd:
            config = ConfigToTestWith(file_name='test_good.ini')
            self._test_simple_example_config(config)
            mock_cwd.assert_called()

    def test_read_cwd_deeper_start(self):
        with mock.patch("os.getcwd", return_value=os.path.join(self.get_test_files_path(), 'deeper_dir')) as mock_cwd:
            config = ConfigToTestWith(file_name='test_good.ini')
            self._test_simple_example_config(config)
            mock_cwd.assert_called()

    def test_does_not_exist(self):
        with self.assertRaises(FileNotFoundError):
            _ = ConfigToTestWith(file_name='test_good.ini')

    def test_read_no_password(self):
        with self.assertRaises(pydantic.ValidationError):
            _ = ConfigToTestWith(
                file_name='test_no_pw.ini',
                start_path=self.get_test_files_path()
            )

    def test_missing_section(self):
        with self.assertRaises(pydantic.ValidationError):
            _ = ConfigToTestWith(
                file_name='test_no_pw.ini',
                start_path=self.get_test_files_path()
            )

    def test_bad_interpolations(self):
        with self.assertRaises(ValueError):
            _ = ConfigToTestWith(
                file_name='test_bad_interpolations.ini',
                start_path=self.get_test_files_path()
            )

    def test_read_keepass_good(self):
        try:
            from pykeepass import PyKeePass
        except ImportError:
            PyKeePass = None

        try:
            os.environ['test_settings_config_files_path'] = str(self.get_test_files_path())
            config = ConfigWithKeypass(
                file_name='test_keepass_good.ini',
                start_path=self.get_test_files_path()
            )
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
                file_name='test_keepass_bad_missing.ini',
                start_path=self.get_test_files_path()
            )
        exc_str = str(raises_cm.exception)
        print("Exception str")
        print(exc_str)
        self.assertIn('Field required', exc_str)
        self.assertIn('database_path', exc_str)

    def test_read_keepass_bad_values(self):
        os.environ['test_settings_config_files_path'] = str(self.get_test_files_path())
        with self.assertRaises(ValueError) as raises_cm:
            _ = ConfigWithKeypass(
                file_name='test_keepass_bad_values.ini',
                start_path=self.get_test_files_path()
            )
        exc_str = str(raises_cm.exception)
        print("Exception str")
        print(exc_str)
        self.assertIn('NOT_AN_INT', exc_str)
        self.assertIn('accidental', exc_str)

    def test_read_keepass_bad2(self):
        os.environ['test_settings_config_files_path'] = str(self.get_test_files_path())
        with self.assertRaises(ValueError) as raises_cm:
            config = ConfigWithBadKeypass(
                file_name='test_keepass_bad_missing_entirely.ini',
                start_path=self.get_test_files_path()
            )
            config.target_database.get_password()
        exc_str = str(raises_cm.exception)
        print("Exception str")
        print(exc_str)
        self.assertIn("keepass_config",  exc_str)

    def test_read_keepass_bad_group(self):
        try:
            from pykeepass import PyKeePass

            os.environ['test_settings_config_files_path'] = str(self.get_test_files_path())
            config = ConfigWithKeypass(
                file_name='test_keepass_good.ini',
                start_path=self.get_test_files_path()
            )

            config.target_database.keepass_group = 'bad'
            with self.assertRaises(ValueError) as raises_cm:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    config.target_database.get_password()
            exc_str = str(raises_cm.exception)
            print("Exception str")
            print(exc_str)
            self.assertIn("group 'bad'", exc_str)
            self.assertIn("not found", exc_str)

        except ImportError:
            self.skipTest(f"Test requires pykeepass")

    def test_read_keepass_bad_userid(self):
        try:
            from pykeepass import PyKeePass

            os.environ['test_settings_config_files_path'] = str(self.get_test_files_path())
            config = ConfigWithKeypass(
                file_name='test_keepass_good.ini',
                start_path=self.get_test_files_path()
            )

            config.target_database.user_id = 'bad'
            with self.assertRaises(ValueError) as raises_cm:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    config.target_database.get_password()
            exc_str = str(raises_cm.exception)
            print("Exception str")
            print(exc_str)
            self.assertIn("does not have entry for", exc_str)
            self.assertIn("'bad'", exc_str)

        except ImportError:
            self.skipTest(f"Test requires pykeepass")

    def test_read_keepass_sub_good(self):
        try:
            from pykeepass import PyKeePass
        except ImportError:
            PyKeePass = None

        try:
            os.environ['test_settings_config_files_path'] = str(self.get_test_files_path())
            config = ConfigWithTestFilePath(
                file_name='test_keepass_good_keepass_sub.ini',
                start_path=self.get_test_files_path()
            )
            self.assertEqual(config.target_database.get_password(), 'b2g4VhNSKegFMtxo49Dz')

        except (ValueError, ImportError) as e:
            if "No module named 'pykeepass" in str(e):
                if PyKeePass is None:
                    self.skipTest(f"Test requires pykeepass")
                else:
                    raise "pykeepass imported by test but not by config_wrangler"
            else:
                raise

    def test_read_keepass_shared_sub_good(self):
        try:
            from pykeepass import PyKeePass
        except ImportError:
            PyKeePass = None

        try:
            os.environ['test_settings_config_files_path'] = str(self.get_test_files_path())
            config = ConfigWithTestFilePath(
                file_name='test_keepass_good_keepass_shared_sub.ini',
                start_path=self.get_test_files_path()
            )
            self.assertEqual(config.target_database.get_password(), 'b2g4VhNSKegFMtxo49Dz')

        except (ValueError, ImportError) as e:
            if "No module named 'pykeepass" in str(e):
                if PyKeePass is None:
                    self.skipTest(f"Test requires pykeepass")
                else:
                    raise "pykeepass imported by test but not by config_wrangler"
            else:
                raise

    def test_read_sub_keepass_bad1(self):
        with self.assertRaises(ValueError) as raises_cm:
            _ = ConfigToTestWith(
                file_name='test_keepass_bad_missing_sub.ini',
                start_path=self.get_test_files_path()
            )
        exc_str = str(raises_cm.exception)
        print("Exception str")
        print(exc_str)
        self.assertIn('database_path', exc_str)
        self.assertIn('Field required', exc_str)

    def test_read_shared_sub_keepass_bad1(self):
        with self.assertRaises(ValueError) as raises_cm:
            _ = ConfigToTestWith(
                file_name='test_keepass_bad_missing_shared_sub.ini',
                start_path=self.get_test_files_path()
            )
        exc_str = str(raises_cm.exception)
        print("Exception str")
        print(exc_str)
        self.assertIn('Field required', exc_str)
        self.assertIn('database_path', exc_str)

    def test_read_keyring_good(self):
        try:
            import keyring
        except ImportError:
            keyring = None

        try:
            password = 'mysuperpassword'
            if keyring is not None:
                # If keyring is actually installed, use it to set the password
                keyring.set_password('example_section', 'python_unittester_01', password)
            config = ConfigToTestWith(
                file_name='test_keyring.ini',
                start_path=self.get_test_files_path()
            )
            self.assertEqual(config.target_database.get_password(), password)

            d = config.model_dump()
            self.assertEqual(d['test_section']['my_url'], config.test_section.my_url)
            self.assertEqual(d['test_section']['my_int'], config.test_section.my_int)
        except (ValueError, ImportError) as e:
            if "No module named 'keyring'" in str(e):
                if keyring is None:
                    self.skipTest(f"Test requires keyring")
                else:
                    raise "keyring imported by test but not by config_wrangler"
            else:
                raise

    def test_env_password_direct_1(self):
        class Config1(ConfigRoot):
            test1: Credentials

        password = '1$password'
        os.environ['test1_password'] = password

        config = Config1(test1={
            'user_id': 'user1',
            'password_source': 'ENVIRONMENT',
        })

        self.assertEqual(config.test1.get_password(), password)

    def test_env_password_direct_2(self):
        class Config1(ConfigRoot):
            test2: Credentials

        password = '2$password'
        os.environ['user2'] = password

        config = Config1(test2={
            'user_id': 'user2',
            'password_source': 'ENVIRONMENT',
        })

        self.assertEqual(config.test2.get_password(), password)

    def test_env_password_direct_3(self):
        class Config1(ConfigRoot):
            test3: Credentials

        password = '3$password'
        os.environ['Password_user3'] = password

        config = Config1(test3={
            'user_id': 'user3',
            'password_source': 'ENVIRONMENT',
        })

        self.assertEqual(config.test3.get_password(), password)

    def test_env_password_keypass(self):
        class ConfigEnvKeypass(ConfigRoot):
            test: Credentials

        # Store the keepass password in envt that will be read in
        # since password.keepass.password_source is ENVIRONMENT
        os.environ['KEEPASS_PASSWORD'] = 'supersecret_encryption_password'

        config = ConfigEnvKeypass(**{
            'test': {
                'user_id': 'python_unittester_01',
                'password_source': 'KEEPASS',
                "keepass_group": "aws",
            },
            'passwords': {
                'keepass': {
                    'database_path': "keepass_db.kdbx",
                    'password_source': 'ENVIRONMENT',
                }
            }
        })
        password = 'b2g4VhNSKegFMtxo49Dz'
        self.assertEqual(password, config.test.get_password())
