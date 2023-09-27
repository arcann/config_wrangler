import inspect
from pathlib import Path


class Base_Tests_Mixin:
    @staticmethod
    def get_package_path() -> Path:
        module_path = inspect.getfile(Base_Tests_Mixin)
        return Path(module_path).parent

    def get_test_files_path(self):
        return self.get_package_path() / 'test_config_files'
