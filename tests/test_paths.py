import os
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from pydantic import ValidationError

from config_wrangler.config_templates.config_hierarchy import ConfigHierarchy
from config_wrangler.config_types.path_types import (
    PathExpandUser, DirectoryExpandUser, AutoCreateDirectoryPath,
    AutoCreateDirectory, PathFindUp, DirectoryFindUp, PathFindUpExpandUser, DirectoryFindUpExpandUser, ExecutablePath,
)


class TestIniParse(unittest.TestCase):

    @staticmethod
    def _make_expand_user(user_path: Path):
        def fake_expand_user(path: Path):
            path_str = str(path)
            if path_str[0] == '~':
                new_path_str = str(user_path) + path_str[1:]
                newpath = Path(new_path_str)
            else:
                newpath = path
            return newpath
        return fake_expand_user

    def test_file_expand_user(self):
        class TestConfig(ConfigHierarchy):
            exp_user_path: PathExpandUser

        with TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            actual_file = tmp_path / "my_file.txt"
            with open(actual_file, 'wt') as f:
                f.write('I exist')
            with patch.object(Path, 'expanduser', new=self._make_expand_user(tmp_path)):
                test_path_str = '~/my_file.txt'
                config = TestConfig(exp_user_path=test_path_str)
                self.assertEqual(config.exp_user_path, actual_file)

    def test_file_expand_user_not_exist(self):
        class TestConfig(ConfigHierarchy):
            exp_user_path: PathExpandUser

        with TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            with self.assertRaises(ValidationError):
                with patch.object(Path, 'expanduser', new=self._make_expand_user(tmp_path)):
                    test_path_str = '~/my_file.txt'
                    _ = TestConfig(exp_user_path=test_path_str)

    def test_dir_expand_user(self):
        class TestConfig(ConfigHierarchy):
            exp_user_path: DirectoryExpandUser

        with TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            actual_dir = tmp_path / "sub_dir"
            actual_dir.mkdir()
            with patch.object(Path, 'expanduser', new=self._make_expand_user(tmp_path)):
                test_path_str = '~/sub_dir'
                config = TestConfig(exp_user_path=test_path_str)
                self.assertEqual(config.exp_user_path, actual_dir)

    def test_dir_expand_user_not_exist(self):
        class TestConfig(ConfigHierarchy):
            exp_user_path: DirectoryExpandUser

        with TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            with self.assertRaises(ValidationError):
                with patch.object(Path, 'expanduser', new=self._make_expand_user(tmp_path)):
                    test_path_str = '~/sub_dir'
                    _ = TestConfig(exp_user_path=test_path_str)

    def test_autocreate_dir_expand_user(self):
        class TestConfig(ConfigHierarchy):
            exp_user_path: AutoCreateDirectory

        with TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            sub_dir = "sub_dir"
            actual_dir = tmp_path / sub_dir
            with patch.object(Path, 'expanduser', new=self._make_expand_user(tmp_path)):
                test_path_str = f'~/{sub_dir}'
                config = TestConfig(exp_user_path=test_path_str)
                self.assertEqual(config.exp_user_path, actual_dir)
                self.assertTrue(config.exp_user_path.exists())
                self.assertTrue(config.exp_user_path.is_dir())

    def test_autocreate_dir_expand_user_old_name(self):
        class TestConfig(ConfigHierarchy):
            exp_user_path: AutoCreateDirectoryPath

        with TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            sub_dir = "sub_dir"
            actual_dir = tmp_path / sub_dir
            with patch.object(Path, 'expanduser', new=self._make_expand_user(tmp_path)):
                test_path_str = f'~/{sub_dir}'
                config = TestConfig(exp_user_path=test_path_str)
                self.assertEqual(config.exp_user_path, actual_dir)
                self.assertTrue(config.exp_user_path.exists())
                self.assertTrue(config.exp_user_path.is_dir())

    def test_autocreate_dir_expand_user_invalid(self):
        class TestConfig(ConfigHierarchy):
            exp_user_path: AutoCreateDirectory

        with TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            folder_name = "folder_with\0_null_char"
            actual_dir = tmp_path / folder_name
            with patch.object(Path, 'expanduser', new=self._make_expand_user(tmp_path)):
                with self.assertRaises(ValidationError):
                    test_path_str = f"~/{folder_name}"
                    _ = TestConfig(exp_user_path=test_path_str)

    def test_autocreate_dir_abs(self):
        class TestConfig(ConfigHierarchy):
            abs_path: AutoCreateDirectory

        with TemporaryDirectory() as tmp_dir:
            actual_dir = Path(tmp_dir) / "sub_dir"
            test_path_str = str(actual_dir)
            config = TestConfig(abs_path=test_path_str)
            self.assertEqual(config.abs_path, actual_dir)
            self.assertTrue(config.abs_path.exists())
            self.assertTrue(config.abs_path.is_dir())

    def test_path_find_up(self):
        class TestConfig(ConfigHierarchy):
            find_me_path: PathFindUp

        with TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            test_filename = "test.csv"
            actual_file = tmp_path / test_filename
            with open(actual_file, 'wt') as f:
                f.write('data,file,exists,here')
            sub_dir = tmp_path / 'sub_dir'
            sub_dir.mkdir()
            with patch("os.getcwd", return_value=str(sub_dir)):
                test_path_str = test_filename
                config = TestConfig(find_me_path=test_path_str)
                self.assertEqual(config.find_me_path, actual_file)

    def test_path_find_up_not_found(self):
        class TestConfig(ConfigHierarchy):
            find_me_path: PathFindUp

        with TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            test_filename = "test.csv"
            actual_file = tmp_path / test_filename
            sub_dir = tmp_path / 'sub_dir'
            sub_dir.mkdir()
            with self.assertRaises(ValidationError):
                with patch("os.getcwd", return_value=str(sub_dir)):
                    test_path_str = test_filename
                    config = TestConfig(find_me_path=test_path_str)
                    self.assertEqual(config.find_me_path, actual_file)

    def test_dir_find_up_a(self):
        class TestConfig(ConfigHierarchy):
            find_me_path: DirectoryFindUp

        with TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            test_filename = "sub1"
            actual_dir = tmp_path / test_filename
            cwd = actual_dir / 'sub2'
            cwd.mkdir(parents=True)
            with patch("os.getcwd", return_value=str(cwd)):
                test_path_str = test_filename
                config = TestConfig(find_me_path=test_path_str)
                self.assertEqual(config.find_me_path, actual_dir)

    def test_dir_find_up_b(self):
        class TestConfig(ConfigHierarchy):
            find_me_path: DirectoryFindUp

        with TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            test_filename = "sub1"
            actual_dir = tmp_path / test_filename
            actual_dir.mkdir(parents=True)
            cwd = tmp_path / 'sub2' / 'sub2.2'
            cwd.mkdir(parents=True)
            with patch("os.getcwd", return_value=str(cwd)):
                test_path_str = test_filename
                config = TestConfig(find_me_path=test_path_str)
                self.assertEqual(config.find_me_path, actual_dir)

    def test_dir_find_up_not_found(self):
        class TestConfig(ConfigHierarchy):
            find_me_path: DirectoryFindUp

        with TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            test_filename = "sub1"
            actual_dir = tmp_path / test_filename
            cwd = tmp_path / 'sub2' / 'sub2.2'
            cwd.mkdir(parents=True)
            with self.assertRaises(ValidationError):
                with patch("os.getcwd", return_value=str(cwd)):
                    test_path_str = test_filename
                    config = TestConfig(find_me_path=test_path_str)
                    self.assertEqual(config.find_me_path, actual_dir)

    def test_path_find_up_exp_user_rel(self):
        class TestConfig(ConfigHierarchy):
            find_me_path: PathFindUpExpandUser

        with TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            test_filename = "test.csv"
            actual_file = tmp_path / test_filename
            with open(actual_file, 'wt') as f:
                f.write('data,file,exists,here')
            sub_dir = tmp_path / 'sub_dir'
            sub_dir.mkdir()
            with patch("os.getcwd", return_value=str(sub_dir)):
                with patch.object(Path, 'expanduser', new=self._make_expand_user(Path('---bad_path---'))):
                    test_path_str = test_filename
                    config = TestConfig(find_me_path=test_path_str)
                    self.assertEqual(config.find_me_path, actual_file)

    def test_path_find_up_exp_user_abs(self):
        class TestConfig(ConfigHierarchy):
            find_me_path: PathFindUpExpandUser

        with TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            test_filename = "test.csv"
            actual_file = tmp_path / test_filename
            with open(actual_file, 'wt') as f:
                f.write('data,file,exists,here')
            sub_dir = tmp_path / 'sub_dir'
            sub_dir.mkdir()

            with patch("os.getcwd", return_value=str(sub_dir)):
                with patch.object(Path, 'expanduser', new=self._make_expand_user(tmp_path)):
                    test_path_str = str(actual_file)
                    config = TestConfig(find_me_path=test_path_str)
                    self.assertEqual(config.find_me_path, actual_file)

    def test_path_find_up_exp_user_user(self):
        class TestConfig(ConfigHierarchy):
            find_me_path: PathFindUpExpandUser

        with TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            test_filename = "test.csv"
            actual_file = tmp_path / test_filename
            with open(actual_file, 'wt') as f:
                f.write('data,file,exists,here')
            sub_dir = tmp_path / 'sub_dir'
            sub_dir.mkdir()

            with patch("os.getcwd", return_value=str(sub_dir)):
                with patch.object(Path, 'expanduser', new=self._make_expand_user(tmp_path)):
                    test_path = Path('~') / test_filename
                    test_path_str = str(test_path)
                    config = TestConfig(find_me_path=test_path_str)
                    self.assertEqual(config.find_me_path, actual_file)

    def test_path_find_up_exp_user_rel_not_found(self):
        class TestConfig(ConfigHierarchy):
            find_me_path: PathFindUpExpandUser

        with TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            test_filename = "test.csv"
            sub_dir = tmp_path / 'sub_dir'
            sub_dir.mkdir()
            with patch("os.getcwd", return_value=str(sub_dir)):
                with patch.object(Path, 'expanduser', new=self._make_expand_user(tmp_path)):
                    with self.assertRaises(ValidationError):
                        test_path_str = test_filename
                        _ = TestConfig(find_me_path=test_path_str)

    def test_path_find_up_exp_user_abs_not_found(self):
        class TestConfig(ConfigHierarchy):
            find_me_path: PathFindUpExpandUser

        with TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            test_filename = "test.csv"
            actual_file = tmp_path / test_filename
            sub_dir = tmp_path / 'sub_dir'
            sub_dir.mkdir()

            with patch("os.getcwd", return_value=str(sub_dir)):
                with patch.object(Path, 'expanduser', new=self._make_expand_user(tmp_path)):
                    with self.assertRaises(ValidationError):
                        test_path_str = str(actual_file)
                        _ = TestConfig(find_me_path=test_path_str)

    def test_path_find_up_exp_user_user_not_found(self):
        class TestConfig(ConfigHierarchy):
            find_me_path: PathFindUpExpandUser

        with TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            test_filename = "test.csv"
            sub_dir = tmp_path / 'sub_dir'
            sub_dir.mkdir()

            with patch("os.getcwd", return_value=str(sub_dir)):
                with patch.object(Path, 'expanduser', new=self._make_expand_user(tmp_path)):
                    with self.assertRaises(ValidationError):
                        test_path = Path('~') / test_filename
                        test_path_str = str(test_path)
                        _ = TestConfig(find_me_path=test_path_str)

## ----------- DIR versions
    def test_dir_find_up_exp_user_rel(self):
        class TestConfig(ConfigHierarchy):
            find_me_path: DirectoryFindUpExpandUser

        with TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            test_dir = "test_dir"
            actual_dir = tmp_path / test_dir
            actual_dir.mkdir()
            sub_dir = tmp_path / 'sub_dir'
            sub_dir.mkdir()
            with patch("os.getcwd", return_value=str(sub_dir)):
                with patch.object(Path, 'expanduser', new=self._make_expand_user(Path('---bad_path---'))):
                    test_path_str = test_dir
                    config = TestConfig(find_me_path=test_path_str)
                    self.assertEqual(config.find_me_path, actual_dir)

    def test_dir_find_up_exp_user_abs(self):
        class TestConfig(ConfigHierarchy):
            find_me_path: DirectoryFindUpExpandUser

        with TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            test_path = "test_path2"
            actual_path = tmp_path / test_path
            actual_path.mkdir()
            sub_dir = tmp_path / 'sub_dir'
            sub_dir.mkdir()

            with patch("os.getcwd", return_value=str(sub_dir)):
                with patch.object(Path, 'expanduser', new=self._make_expand_user(tmp_path)):
                    test_path_str = str(actual_path)
                    config = TestConfig(find_me_path=test_path_str)
                    self.assertEqual(config.find_me_path, actual_path)

    def test_dir_find_up_exp_user_user(self):
        class TestConfig(ConfigHierarchy):
            find_me_path: DirectoryFindUpExpandUser

        with TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            test_path = "blue"
            actual_path = tmp_path / test_path
            actual_path.mkdir()
            sub_dir = tmp_path / 'sub_dir'
            sub_dir.mkdir()

            with patch("os.getcwd", return_value=str(sub_dir)):
                with patch.object(Path, 'expanduser', new=self._make_expand_user(tmp_path)):
                    test_path = Path('~') / test_path
                    test_path_str = str(test_path)
                    config = TestConfig(find_me_path=test_path_str)
                    self.assertEqual(config.find_me_path, actual_path)

    def test_dir_find_up_exp_user_rel_not_found(self):
        class TestConfig(ConfigHierarchy):
            find_me_path: DirectoryFindUpExpandUser

        with TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            test_path = "red"
            sub_dir = tmp_path / 'sub_dir'
            sub_dir.mkdir()
            with patch("os.getcwd", return_value=str(sub_dir)):
                with patch.object(Path, 'expanduser', new=self._make_expand_user(tmp_path)):
                    with self.assertRaises(ValidationError):
                        test_path_str = test_path
                        _ = TestConfig(find_me_path=test_path_str)

    def test_dir_find_up_exp_user_abs_not_found(self):
        class TestConfig(ConfigHierarchy):
            find_me_path: DirectoryFindUpExpandUser

        with TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            test_path = "green"
            actual_path = tmp_path / test_path
            sub_dir = tmp_path / 'sub_dir'
            sub_dir.mkdir()

            with patch("os.getcwd", return_value=str(sub_dir)):
                with patch.object(Path, 'expanduser', new=self._make_expand_user(tmp_path)):
                    with self.assertRaises(ValidationError):
                        test_path_str = str(actual_path)
                        _ = TestConfig(find_me_path=test_path_str)

    def test_dir_find_up_exp_user_user_not_found(self):
        class TestConfig(ConfigHierarchy):
            find_me_path: DirectoryFindUpExpandUser

        with TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            test_path = "purple"
            sub_dir = tmp_path / 'sub_dir'
            sub_dir.mkdir()

            with patch("os.getcwd", return_value=str(sub_dir)):
                with patch.object(Path, 'expanduser', new=self._make_expand_user(tmp_path)):
                    with self.assertRaises(ValidationError):
                        test_path = Path('~') / test_path
                        test_path_str = str(test_path)
                        _ = TestConfig(find_me_path=test_path_str)

    def test_exec_path_find(self):
        class TestConfig(ConfigHierarchy):
            find_me_path: ExecutablePath

        python_ex_path = Path(sys.executable)
        python_path = python_ex_path.parent
        python_name = python_ex_path.name

        saved_path = os.environ['PATH']
        try:
            # Manually build a path to this python
            paths = [
                '/probably_does_not_exist',
                str(python_path),
                '/probably_also_does_not_exist',
            ]
            os.environ['PATH'] = os.pathsep.join(paths)

            config = TestConfig(find_me_path=python_name)
            self.assertEqual(config.find_me_path, python_ex_path)
        finally:
            os.environ['PATH'] = saved_path

    def test_exec_path_find_not_found(self):
        class TestConfig(ConfigHierarchy):
            find_me_path: ExecutablePath

        python_ex_path = Path(sys.executable)
        python_path = python_ex_path.parent

        saved_path = os.environ['PATH']
        try:
            paths = [
                '/probably_does_not_exist',
                str(python_path),
                '/probably_also_does_not_exist',
            ]
            os.environ['PATH'] = os.pathsep.join(paths)

            with self.assertRaises(ValidationError):
                _ = TestConfig(find_me_path='who_would_name_a_file_this')
        finally:
            os.environ['PATH'] = saved_path
