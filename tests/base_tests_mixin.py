import inspect
from pathlib import Path


class Base_Tests_Mixin:
    def get_package_path(self) -> Path:
        module_path = inspect.getfile(self.__class__)
        return Path(module_path).parent

    def get_test_files_path(self):
        return self.get_package_path() / 'test_config_files'
