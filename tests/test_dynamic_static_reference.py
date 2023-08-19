import unittest
from typing import List, Dict

from config_wrangler.config_from_ini_env import ConfigFromIniEnv
from config_wrangler.config_templates.config_hierarchy import ConfigHierarchy
from config_wrangler.config_types.dynamically_referenced import DynamicallyReferenced
from tests.base_tests_mixin import Base_Tests_Mixin


class Product(ConfigHierarchy):
    name: str
    weight: int


class Car(Product):
    manufacturer: str


class TestReferenceSection(ConfigHierarchy):
    # NOTE: In these types of dynamic references, the config will have a list of strings
    #       which will be parsed as such and then since the class contained in the List
    #       or Dict is itself a DynamicallyReferenced special class we'll:
    #         1) Ensure it's a valid reference
    #         2) Elsewhere in the model load we will instantiate the proper ConfigHierarchy subclass
    #            for the referenced items.
    #         3) Provide a method get_referenced that will get that referenced ConfigHierarchy instance
    #       Notably, in this case each referenced object can be of a different type (Product or Car in this test).
    list_of_products: List[DynamicallyReferenced]
    dict_of_products: Dict[str, DynamicallyReferenced]


class TestDynamicConfig(ConfigFromIniEnv):
    main_section: TestReferenceSection

    apple: Product
    pear: Product
    banana: Product
    ford_model_t: Car


class TestDynamicStaticRef(unittest.TestCase, Base_Tests_Mixin):
    def setUp(self):
        self.test_files_path = self.get_test_files_path()

    def tearDown(self):
        pass

    def test_dynamic_good_direct(self):
        config = TestDynamicConfig(
            file_name=self.test_files_path / 'dynamic' / 'good.ini',
        )
        list_of_products = config.main_section.list_of_products
        self.assertEqual(len(list_of_products), 4)
        product1 = list_of_products[0].get_referenced()
        product2 = list_of_products[1].get_referenced()
        product3 = list_of_products[2].get_referenced()
        product4 = list_of_products[3].get_referenced()

        self.assertEqual(product1.name, 'Granny Smith')
        self.assertEqual(product2.name, 'Over-ripe')
        self.assertEqual(product3.name, 'Best Pear')
        self.assertEqual(product4.name, 'Model T')
        self.assertEqual(product1.weight, 15)
        self.assertEqual(product2.weight, 10)
        self.assertEqual(product3.weight, 18)
        self.assertEqual(product4.weight, 750000)

        # Note: In this case the Model T was read is a Car,
        #       so it should have a manufacturer
        self.assertEqual(product4.manufacturer, 'Ford')

        # TODO: Test the dict_of_products

    def test_dynamic_static_bad_instance(self):
        with self.assertRaises(ValueError) as raises_cm:
            _ = TestDynamicConfig(
                file_name=self.test_files_path / 'dynamic' / 'bad_instance.ini',
            )
        exc_str = str(raises_cm.exception)
        print("Exception str")
        print(exc_str)
        self.assertIn('weight', exc_str)
        self.assertIn('Field required', exc_str)

    def test_dynamic_bad_ref(self):
        with self.assertRaises(ValueError) as raises_cm:
            _ = TestDynamicConfig(
                file_name=self.test_files_path / 'dynamic' / 'bad_reference.ini',
            )
        exc_str = str(raises_cm.exception)
        print("Exception str")
        print(exc_str)
        self.assertIn('main_section', exc_str)
        self.assertIn('list_of_products', exc_str)
        self.assertIn('bad_product', exc_str)
