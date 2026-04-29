import unittest
from typing import List, Dict

from pydantic import Field
from typing_extensions import Annotated

from config_wrangler.config_from_ini_env import ConfigFromIniEnv
from config_wrangler.config_templates.config_hierarchy import ConfigHierarchy
from config_wrangler.config_types.delimited_field import DelimitedListField
from tests.base_tests_mixin import Base_Tests_Mixin


class Product(ConfigHierarchy):
    product_type: str
    grows_on_plants: bool
    name: str
    weight: int
    color: str = 'Not available'


class EdibleProduct(Product):
    """ Extends the generic Product with extra attributes """
    calories: int


class TestReferenceSection(ConfigHierarchy):
    # NOTE: In these types of dynamic references, the config will have a list of strings
    #       which will be parsed as such and then since the class contained in the List
    #       or Dict is itself a ConfigHierarchy, we'll find the config data to instantiate
    #       those object instances. All instances will be of Product type, or a subclass.
    list_of_products_c: List[Product] = DelimitedListField()
    list_of_products_nl: Annotated[List[Product], DelimitedListField(delimiter='\n')]
    dict_of_products: Dict[str, Product]
    list_of_str: Annotated[List[str], Field(default_factory=list)]


class TestDynamicConfig(ConfigFromIniEnv):
    main_section: TestReferenceSection


class TestDynamicDynamicRef(unittest.TestCase, Base_Tests_Mixin):
    def setUp(self):
        self.test_files_path = self.get_test_files_path()

    def tearDown(self):
        pass

    def test_dynamic_good_direct(self):
        config = TestDynamicConfig(
            file_name=self.test_files_path / 'dynamic' / 'good_dynamic.ini',
        )
        config_sec = config.main_section

        # Note: This style does not work with single item values
        #       (although it can be a list of one value)
        #       So this test skips testing single_product

        self.assertEqual(3, len(config_sec.list_of_str))
        self.assertIn('one', config_sec.list_of_str)
        self.assertIn('two', config_sec.list_of_str)
        self.assertIn('three', config_sec.list_of_str)

        for list_of_products in [
            config_sec.list_of_products_c,
            config_sec.list_of_products_nl,
        ]:
            self.assertEqual(len(list_of_products), 4)
            product1 = list_of_products[0]
            product2 = list_of_products[1]
            product3 = list_of_products[2]
            product4 = list_of_products[3]

            self.assertEqual('Granny Smith', product1.name)
            self.assertEqual('Green', product1.color)
            self.assertEqual('Fruit', product1.product_type)

            self.assertEqual('Over-ripe', product2.name)
            self.assertEqual('Green', product2.color)
            # banana is EdibleProduct and has an extra attribute calories
            self.assertIsInstance(product2, EdibleProduct)
            self.assertEqual(105, product2.calories)

            self.assertEqual('Best Pear', product3.name)
            self.assertEqual('Yellow', product3.color)

            self.assertEqual('Model T', product4.name)
            self.assertEqual('Not available', product4.color)
            self.assertEqual('Vehicle', product4.product_type)
            self.assertEqual(15, product1.weight)
            self.assertEqual(10, product2.weight)
            self.assertEqual(18, product3.weight)
            self.assertEqual(750000, product4.weight)
            # Note: In this case the Model T was read is a generic Product,
            #       so it will not have a manufacturer
            with self.assertRaises(AttributeError):
                _ = product4.manufacturer

        # Test the dict_of_products
        dict_of_products = config.main_section.dict_of_products
        self.assertEqual('Granny Smith', dict_of_products['apple'].name)
        self.assertEqual('Over-ripe', dict_of_products['banana'].name)
        self.assertEqual(105, dict_of_products['banana'].calories)

    def test_dynamic_bad_instance(self):
        with self.assertRaises(ValueError) as raises_cm:
            _ = TestDynamicConfig(
                file_name=self.test_files_path / 'dynamic' / 'bad_instance.ini',
            )
        exc_str = str(raises_cm.exception)
        print("Exception str")
        print(exc_str)
        self.assertIn('main_section', exc_str)
        self.assertIn('list_of_products_c', exc_str)
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
        self.assertIn('list_of_products_c', exc_str)
        self.assertIn('bad_product', exc_str)
