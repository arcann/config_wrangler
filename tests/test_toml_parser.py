import os
import warnings
from unittest import mock

import pydantic

from config_wrangler.config_from_toml_env import ConfigFromTomlEnv
from config_wrangler.config_templates.config_hierarchy import ConfigHierarchy
from config_wrangler.config_templates.keepass_config import KeepassConfig
from tests.test_ini_parser import TestSection, TestIniParser, TestSettings
from tests.simulate_database import SimDatabase

class ConfigToTestWith(ConfigFromTomlEnv):
    target_database: SimDatabase

    test_section: TestSection


class ConfigWithTestFilePath(ConfigToTestWith):
    test_settings: TestSettings


class ConfigWithKeypass(ConfigWithTestFilePath):
    keepass: KeepassConfig


class FakeKeepassConfig(ConfigHierarchy):
    pass


class ConfigWithBadKeypass(ConfigToTestWith):
    keepass: FakeKeepassConfig


class TestTomlParser(TestIniParser):

    def get_test_files_path(self):
        return self.get_package_path() / 'test_config_files_toml'

    def test_read_start_path(self):
        config = ConfigToTestWith(
            file_name='test_good.toml',
            start_path=self.get_test_files_path()
        )
        self._test_simple_example_config(config)

    def test_read_start_path_deeper_start(self):
        config = ConfigToTestWith(
            file_name='test_good.toml',
            start_path=os.path.join(self.get_test_files_path(), 'deeper_dir')
        )
        self._test_simple_example_config(config)

    def test_read_start_path_deeper_start_2(self):
        config = ConfigToTestWith(
            file_name='test_good.toml',
            start_path=os.path.join(self.get_test_files_path(), 'deeper_dir', 'deeper_does_not_exist')
        )
        self._test_simple_example_config(config)

    def test_read_cwd(self):
        with mock.patch("os.getcwd", return_value=self.get_test_files_path()) as mock_cwd:
            config = ConfigToTestWith(file_name='test_good.toml')
            self._test_simple_example_config(config)
            mock_cwd.assert_called()

    def test_read_cwd_deeper_start(self):
        with mock.patch("os.getcwd", return_value=os.path.join(self.get_test_files_path(), 'deeper_dir')) as mock_cwd:
            config = ConfigToTestWith(file_name='test_good.toml')
            self._test_simple_example_config(config)
            mock_cwd.assert_called()

    def test_does_not_exist(self):
        with self.assertRaises(FileNotFoundError):
            _ = ConfigToTestWith(file_name='test_good.toml')

    def test_read_no_password(self):
        with self.assertRaises(pydantic.ValidationError):
            _ = ConfigToTestWith(
                file_name='test_no_pw.toml',
                start_path=self.get_test_files_path()
            )

    def test_missing_section(self):
        with self.assertRaises(pydantic.ValidationError):
            _ = ConfigToTestWith(
                file_name='test_no_pw.toml',
                start_path=self.get_test_files_path()
            )

    def test_bad_interpolations(self):
        with self.assertRaises(ValueError):
            _ = ConfigToTestWith(
                file_name='test_bad_interpolations.toml',
                start_path=self.get_test_files_path()
            )

    def test_read_keepass_good(self):
        try:
            from pykeepass import PyKeePass
        except ImportError:
            # noinspection PyPep8Naming
            PyKeePass = None

        try:
            os.environ['test_settings_config_files_path'] = str(self.get_test_files_path())
            config = ConfigWithKeypass(
                file_name='test_keepass_good.toml',
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
                file_name='test_keepass_bad_missing.toml',
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
                file_name='test_keepass_bad_values.toml',
                start_path=self.get_test_files_path()
            )
        exc_str = str(raises_cm.exception)
        print("Exception str")
        print(exc_str)
        self.assertIn('NOT_AN_INT', exc_str)
        self.assertIn('${my_INT', exc_str)

    def test_read_keepass_bad2(self):
        os.environ['test_settings_config_files_path'] = str(self.get_test_files_path())
        with self.assertRaises(ValueError) as raises_cm:
            config = ConfigWithBadKeypass(
                file_name='test_keepass_bad_missing_entirely.toml',
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
                file_name='test_keepass_good.toml',
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
                file_name='test_keepass_good.toml',
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
            # noinspection PyPep8Naming
            PyKeePass = None

        try:
            os.environ['test_settings_config_files_path'] = str(self.get_test_files_path())
            config = ConfigWithTestFilePath(
                file_name='test_keepass_good_keepass_sub.toml',
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
            # noinspection PyPep8Naming
            PyKeePass = None

        try:
            os.environ['test_settings_config_files_path'] = str(self.get_test_files_path())
            config = ConfigWithTestFilePath(
                file_name='test_keepass_good_keepass_shared_sub.toml',
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
                file_name='test_keepass_bad_missing_sub.toml',
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
                file_name='test_keepass_bad_missing_shared_sub.toml',
                start_path=self.get_test_files_path()
            )
        exc_str = str(raises_cm.exception)
        print("Exception str")
        print(exc_str)
        self.assertIn('database_path', exc_str)
        self.assertIn('Field required', exc_str)

    def test_read_keyring_good(self):
        try:
            import keyring
        except ImportError:
            keyring = None
        except keyring.errors.NoKeyringError:
            self.skipTest(f"Test requires keyring backend")

        try:
            password = 'mysuperpassword'
            if keyring is not None:
                # If keyring is actually installed, use it to set the password
                keyring.set_password('example_section', 'python_unittester_01', password)
            config = ConfigToTestWith(
                file_name='test_keyring.toml',
                start_path=self.get_test_files_path()
            )
            self.assertEqual(config.target_database.get_password(), password)

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


# Don't test TestIniParser here
del TestIniParser
