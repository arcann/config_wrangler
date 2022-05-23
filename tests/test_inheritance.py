import unittest

from config_wrangler.config_from_ini_env import ConfigFromIniEnv
from config_wrangler.config_templates.config_hierarchy import ConfigHierarchy
from tests.base_tests_mixin import Base_Tests_Mixin


class TestInheritConfigSection(ConfigHierarchy):
    name: str
    child: str
    parent1: str
    parent2: str
    grandparent1_1: str
    grandparent2_1: str
    grandparent2_2: str


class TestInheritConfig(ConfigFromIniEnv):
    section: TestInheritConfigSection


class TestIniParsee(unittest.TestCase, Base_Tests_Mixin):
    def setUp(self):
        self.test_files_path = self.get_test_files_path()

    def tearDown(self):
        pass

    def _test_inheritance_config(self, config: TestInheritConfig):
        self.assertEqual(config.section.name, 'child')
        self.assertEqual(config.section.child, 'Me')
        self.assertEqual(config.section.parent1, '1')
        self.assertEqual(config.section.parent2, '2')
        self.assertEqual(config.section.grandparent1_1, '1.1')
        self.assertEqual(config.section.grandparent2_1, '2.1')
        self.assertEqual(config.section.grandparent2_2, '2.2')

    def test_read_inheritance_folder(self):
        config = TestInheritConfig(
            file_name='child.ini',
            start_path=self.test_files_path / 'inheritance'
        )
        self._test_inheritance_config(config)

    def test_read_inheritance_direct(self):
        config = TestInheritConfig(
            file_name=self.test_files_path / 'inheritance' / 'child.ini',
        )
        self._test_inheritance_config(config)
