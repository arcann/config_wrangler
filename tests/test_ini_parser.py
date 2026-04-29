import os
import unittest
import warnings
from datetime import date, time, datetime
from typing import *
from unittest import mock

from pydantic import Field, AnyHttpUrl, DirectoryPath
from pydantic_core import Url

from config_wrangler.config_from_ini_env import ConfigFromIniEnv
from config_wrangler.config_root import ConfigRoot
from config_wrangler.config_templates.config_hierarchy import ConfigHierarchy
from config_wrangler.config_templates.credentials import Credentials
from config_wrangler.config_templates.keepass_config import KeepassConfig
from config_wrangler.config_types.delimited_field import DelimitedListField
from config_wrangler.config_wrangler_config import ConfigWranglerConfig
from tests.base_tests_mixin import Base_Tests_Mixin
from tests.simulate_database import SimDatabase


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


class TestCommonSection(ConfigHierarchy):
    value_a: str
    value_b: str
    value_c: str


class ConfigCommon(ConfigHierarchy):

    model_config = ConfigWranglerConfig(
        validate_default=True,
        validate_assignment=True,
        validate_credentials=True,
    )

    target_database: SimDatabase

    test_section: TestSection

    test_inherit_section_1: TestCommonSection
    test_inherit_section_2: TestCommonSection
    test_inherit_section_3: TestCommonSection


class ConfigToTestWith(ConfigFromIniEnv, ConfigCommon):
    pass


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
        os.chdir(self.get_package_path())

    def tearDown(self):
        try:
            del os.environ['test_settings_config_files_path']
        except KeyError:
            pass

    def _test_simple_example_config(self, config):
        test_val = config.test_section.my_int
        self.assertEqual(123, test_val, msg='config.test_section.my_int')
        self.assertIsInstance(test_val, int, msg='config.test_section.my_int')

        test_val = config.test_section.my_float
        self.assertAlmostEqual(123.45, test_val, msg='config.test_section.my_float')
        self.assertIsInstance(test_val, float, msg='config.test_section.my_float')

        test_val = config.test_section.my_bool
        self.assertEqual(True, test_val)
        self.assertIsInstance(test_val, bool)

        test_val = config.test_section.my_list_auto_c
        self.assertEqual(['a', 'b', 'c'], test_val)
        self.assertIsInstance(test_val, list)

        test_val = config.test_section.my_list_auto_nl
        self.assertEqual(['a', 'b', 'c'], test_val)
        self.assertIsInstance(test_val, list)

        test_val = config.test_section.my_list_auto_pipe
        self.assertEqual(['a', 'b', 'c'], test_val)
        self.assertIsInstance(test_val, list)

        test_val = config.test_section.my_list_c
        self.assertEqual(['a', 'b', 'c'], test_val)
        self.assertIsInstance(test_val, list)

        test_val = config.test_section.my_list_python
        self.assertEqual(['x', 'y', 'z'], test_val)
        self.assertIsInstance(test_val, list)

        test_val = config.test_section.my_list_json
        self.assertEqual(["J", "S", "O", "N"], test_val)
        self.assertIsInstance(test_val, list)

        test_val = config.test_section.my_list_nl
        self.assertEqual(['a', 'b', 'c'], test_val)
        self.assertIsInstance(test_val, list)

        test_val = config.test_section.my_list_int_c
        self.assertEqual([1, 2, 3], test_val)
        self.assertIsInstance(test_val, list)
        self.assertIsInstance(test_val[0], int)

        test_val = config.test_section.my_tuple_c
        self.assertEqual(('a1', 'b2', 'c3'), test_val)
        self.assertIsInstance(test_val, tuple)

        test_val = config.test_section.my_tuple_nl
        self.assertEqual(('a1', 'b2', 'c3'), test_val)
        self.assertIsInstance(test_val, tuple)

        test_val = config.test_section.my_tuple_int_c
        self.assertEqual((1, 2, 3), test_val)
        self.assertIsInstance(test_val, tuple)
        self.assertIsInstance(test_val[0], int)

        test_val = config.test_section.my_dict
        self.assertEqual(
            {1: 'One', 2: 'Two'},
            test_val,
            msg=f"config.test_section.my_dict got {test_val} expected {{1: 'One', 2: 'Two'}}"
        )
        self.assertIsInstance(test_val, dict)

        test_val = config.test_section.my_dict_str_int
        self.assertEqual(
            {"one": 1, "two": 2},
            test_val,
            msg='config.test_section.my_dict_str_int',
        )
        self.assertIsInstance(test_val, dict)
        self.assertEqual(1, test_val['one'])
        self.assertIsInstance(test_val['one'], int)
        self.assertEqual(2, test_val['two'])

        self.assertEqual(
            {'A', 'B', 'C'},
            config.test_section.my_set,
            msg='config.test_section.my_set',
        )
        self.assertIsInstance(config.test_section.my_set, set)

        self.assertEqual(
            {1, 2, 3},
            config.test_section.my_set_int,
            msg='config.test_section.my_set_int',
        )
        self.assertIsInstance(config.test_section.my_set_int, set)
        for set_val in config.test_section.my_set_int:
            self.assertIsInstance(set_val, int)

        self.assertEqual(
            frozenset({'A', 'B', 'C'}),
            config.test_section.my_frozenset,
            msg='config.test_section.my_frozenset',
        )
        self.assertIsInstance(config.test_section.my_frozenset, frozenset)

        self.assertEqual(
            date(year=2021, month=5, day=31),
            config.test_section.my_date,
            msg='config.test_section.my_date',
        )
        self.assertIsInstance(config.test_section.my_date, date)

        self.assertEqual(
            time(hour=11, minute=55, second=23),
            config.test_section.my_time.replace(tzinfo=None),
            msg='config.test_section.my_time',
        )
        self.assertIsInstance(config.test_section.my_time, time)

        self.assertEqual(
            datetime(year=2021, month=5, day=31, hour=11, minute=23, second=53),
            config.test_section.my_datetime.replace(tzinfo=None),
            msg='config.test_section.my_datetime',
        )
        self.assertIsInstance(config.test_section.my_datetime, datetime)

        self.assertEqual(
            str(Url('https://localhost:6553/')),
            str(config.test_section.my_url),
            msg='config.test_section.my_url',
        )

        self.assertEqual(
            'My DB is in ./example_db',
            config.test_section.double_interpolate,
            msg='double interpolate failed on config.test_section.double_interpolate,'
        )

        self.assertEqual(
            '--**++C++**--',
            config.test_section.triple_interpolate,
            msg='triple interpolate failed on config.test_section.triple_interpolate'
        )

        # Test __inherits_from__
        self.assertEqual(
            # BaseA_${test_section:my_environment:name}
            'BaseA_dev',
            config.test_inherit_section_2.value_a,
            'config.test_inherit_section_2.value_a',
        )
        self.assertEqual(
            # OverrideB_2_${test_section:my_bool}
            'OverrideB_2_ABC☕',
            config.test_inherit_section_2.value_b,
            msg='config.test_inherit_section_2.value_b',
        )
        self.assertEqual(
            'BaseC',
            config.test_inherit_section_2.value_c,
            msg='config.test_inherit_section_2.value_c',
        )

        self.assertEqual(
            # BaseA_${test_section:my_environment:name}
            'BaseA_dev',
            config.test_inherit_section_3.value_a,
            msg='config.test_inherit_section_3.value_a',
        )
        self.assertEqual(
            # OverrideB_2_${test_section:my_bool}
            'OverrideB_2_ABC☕',
            config.test_inherit_section_3.value_b,
            msg='config.test_inherit_section_3.value_b',
        )
        self.assertEqual(
            'OverrideC_3',
            config.test_inherit_section_3.value_c,
            msg='config.test_inherit_section_3.value_c',
        )

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
        with self.assertRaises(ValueError):
            _ = ConfigToTestWith(
                file_name='test_no_pw.ini',
                start_path=self.get_test_files_path()
            )

    def test_missing_section(self):
        with self.assertRaises(ValueError):
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
            self.assertEqual('b2g4VhNSKegFMtxo49Dz', config.target_database.get_password())

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
        self.assertIn("keepass_config", exc_str)

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
            self.assertIn("group", exc_str)
            self.assertIn("'bad'", exc_str)

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
            self.assertEqual('b2g4VhNSKegFMtxo49Dz', config.target_database.get_password())

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
            self.assertEqual('b2g4VhNSKegFMtxo49Dz', config.target_database.get_password())

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
            self.skipTest(f"Test requires keyring")
        except keyring.errors.NoKeyringError:
            self.skipTest(f"Test requires keyring backend")

        try:
            password = 'mysuperpassword'
            keyring.set_password('example_section', 'python_unittester_01', password)
            config = ConfigToTestWith(
                file_name='test_keyring.ini',
                start_path=self.get_test_files_path()
            )
            self.assertEqual(password, config.target_database.get_password())

            d = config.model_dump()
            self.assertEqual(d['test_section']['my_url'], config.test_section.my_url)
            self.assertEqual(d['test_section']['my_int'], config.test_section.my_int)
        except keyring.errors.NoKeyringError:
            self.skipTest(f"Test requires keyring backend")
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

        config = Config1(
            test1={
                'user_id': 'user1',
                'password_source': 'ENVIRONMENT',
            }
        )

        self.assertEqual(password, config.test1.get_password())

    def test_env_password_direct_2(self):
        class Config1(ConfigRoot):
            test2: Credentials

        password = '2$password'
        os.environ['user2'] = password

        config = Config1(
            test2={
                'user_id': 'user2',
                'password_source': 'ENVIRONMENT',
            }
        )

        self.assertEqual(password, config.test2.get_password())

    def test_env_password_direct_3(self):
        class Config1(ConfigRoot):
            test3: Credentials

        password = '3$password'
        os.environ['Password_user3'] = password

        config = Config1(
            test3={
                'user_id': 'user3',
                'password_source': 'ENVIRONMENT',
            }
        )

        self.assertEqual(password, config.test3.get_password())

    def test_env_password_keypass(self):
        try:
            from pykeepass import PyKeePass
        except ImportError:
            raise unittest.SkipTest('pykeepass not installed')

        class ConfigEnvKeypass(ConfigRoot):
            test: Credentials

        # Store the keepass password in envt that will be read in
        # since password.keepass.password_source is ENVIRONMENT
        os.environ['KEEPASS_PASSWORD'] = 'supersecret_encryption_password'

        config = ConfigEnvKeypass(
            **{
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
            }
            )
        password = 'b2g4VhNSKegFMtxo49Dz'
        self.assertEqual(password, config.test.get_password())
