import logging
import os
import unittest
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory

import boto3
import moto
from botocore.exceptions import ClientError
from moto.core import set_initial_no_auth_action_count

from config_wrangler.config_templates.aws.s3_bucket import S3_Bucket, S3_Bucket_Folder
from config_wrangler.config_templates.credentials import PasswordSource
from tests.base_tests_mixin import Base_Tests_Mixin


@moto.mock_s3
class TestS3HelperFunctions(unittest.TestCase, Base_Tests_Mixin):
    def setUp(self):
        logging.basicConfig(level=logging.INFO)
        self.mock_client = boto3.client('s3')
        self.bucket1_name = 'mock_bucket'
        self.mock_client.create_bucket(
            Bucket=self.bucket1_name,
            ACL='private',
        )
        self.bucket2_name = 'mock_bucket2'
        self.bucket2_region = 'us-west-1'
        # noinspection PyTypeChecker
        self.mock_client.create_bucket(
            Bucket=self.bucket2_name,
            CreateBucketConfiguration={
                'LocationConstraint': self.bucket2_region,
            }
        )

        self.bucket3_name = 'mock_bucket3'
        self.bucket3_region = 'eu-central-1'
        # noinspection PyTypeChecker
        self.mock_client.create_bucket(
            Bucket=self.bucket3_name,
            CreateBucketConfiguration={
                'LocationConstraint': self.bucket3_region,
            }
        )

        self.file1_path = self.get_test_files_path() / 'test_good.ini'
        self.file2_path = self.get_test_files_path() / 'test_bad_interpolations.ini'

        self.example1_key = 'test_good.ini'
        self.mock_client.upload_file(
            Bucket=self.bucket1_name,
            Key=self.example1_key,
            Filename=str(self.file1_path)
        )
        self.example2_key = 'folder1/file.txt'
        self.mock_client.upload_file(
            Bucket=self.bucket1_name,
            Key=self.example2_key,
            Filename=str(self.file1_path)
        )

        self.example3_key = 'folder1/file2.txt'
        self.mock_client.upload_file(
            Bucket=self.bucket1_name,
            Key=self.example3_key,
            Filename=str(self.file1_path)
        )

        self.example4_key = 'folder2/file3.txt'
        self.mock_client.upload_file(
            Bucket=self.bucket1_name,
            Key=self.example4_key,
            Filename=str(self.file2_path)
        )

    def test_is_file(self):
        bucket = S3_Bucket(
            bucket_name=self.bucket1_name,
            user_id='mock_user',
            raw_password='super secret password',
            password_source=PasswordSource.CONFIG_FILE,
        )
        file = bucket / self.example1_key
        folder1 = bucket / 'folder1'

        self.assertTrue(file.is_file())
        self.assertFalse(folder1.is_file())

        dne_file = folder1 / 'this_does_not_exist'
        self.assertFalse(dne_file.is_file())

    def test_list_files(self):
        bucket = S3_Bucket(
            bucket_name=self.bucket1_name,
            user_id='mock_user',
            raw_password='super secret password',
            password_source=PasswordSource.CONFIG_FILE,
        )
        contents = bucket.list_object_keys(key=None)
        self.assertIn(self.example1_key, contents)
        self.assertIn(self.example2_key, contents)
        self.assertEqual(len(contents), 4)
        self.assertEqual(bucket.get_bucket_region(), 'us-east-1')

        bucket2 = S3_Bucket(
            bucket_name=self.bucket2_name,
            user_id='mock_user',
            raw_password='super secret password',
            password_source=PasswordSource.CONFIG_FILE,
        )
        contents = bucket2.list_object_keys(key=None)
        self.assertNotIn(self.example1_key, contents)
        self.assertEqual(len(contents), 0)
        self.assertEqual(bucket2.get_bucket_region(), self.bucket2_region)

        bucket3 = S3_Bucket(
            bucket_name=self.bucket3_name,
            user_id='mock_user',
            password_source=PasswordSource.CONFIG_FILE,
            raw_password='super secret password',
        )
        self.assertEqual(bucket3.get_bucket_region(), self.bucket3_region)

    def test_list_bucket_paths(self):
        bucket = S3_Bucket(
            bucket_name=self.bucket1_name,
            user_id='mock_user',
            password_source=PasswordSource.CONFIG_FILE,
            raw_password='super secret password',
        )
        expected = {
            PurePosixPath('test_good.ini'),
            PurePosixPath('folder1/file.txt'),
            PurePosixPath('folder1/file2.txt'),
            PurePosixPath('folder2/file3.txt'),
        }
        actual = set(bucket.list_object_paths())
        self.assertEqual(expected, actual)
        for filename in expected:
            s3_file = bucket / filename
            self.assertTrue(s3_file.exists())

    def test_list_folder_paths(self):
        folder = S3_Bucket_Folder(
            bucket_name=self.bucket1_name,
            folder='folder1',
            user_id='mock_user',
            password_source=PasswordSource.CONFIG_FILE,
            raw_password='super secret password',
        )
        expected = {
            PurePosixPath('file.txt'),
            PurePosixPath('file2.txt'),
        }
        actual = set(folder.list_object_paths())
        self.assertEqual(expected, actual)
        for filename in expected:
            s3_file = folder / filename
            self.assertTrue(s3_file.exists())

    def test_list_folder_iter(self):
        folder = S3_Bucket_Folder(
            bucket_name=self.bucket1_name,
            folder='folder1',
            user_id='mock_user',
            password_source=PasswordSource.CONFIG_FILE,
            raw_password='super secret password',
        )
        actual_set = set()
        for s3_file in folder.iterdir():
            self.assertTrue(s3_file.exists())
            actual_set.add(s3_file.key)

        self.assertIn(self.example2_key, actual_set)
        self.assertIn(self.example3_key, actual_set)
        self.assertEqual(2, len(actual_set))

    def test_deprecated_find_objects(self):
        bucket = S3_Bucket(
            bucket_name=self.bucket1_name,
            user_id='mock_user',
            raw_password='super secret password',
            password_source=PasswordSource.CONFIG_FILE,
        )
        contents = bucket.find_objects(key=None)
        contents_keys = [obj.key for obj in contents]
        self.assertIn(self.example1_key, contents_keys)

    def test_iter_files(self):
        bucket = S3_Bucket(
            bucket_name=self.bucket1_name,
            user_id='mock_user',
            raw_password='super secret password',
            password_source=PasswordSource.CONFIG_FILE,
        )
        contents = list(bucket.iterdir())
        self.assertIn(bucket / self.example1_key, contents)
        self.assertIn(bucket / self.example2_key, contents)

    def test_list_folder_files(self):
        bucket_folder = S3_Bucket_Folder(
            bucket_name=self.bucket1_name,
            folder='folder1',
            user_id='mock_user',
            raw_password='super secret password',
            password_source=PasswordSource.CONFIG_FILE,
        )
        contents = bucket_folder.list_object_keys(key=None)
        self.assertNotIn(self.example1_key, contents)
        self.assertIn(self.example2_key, contents)
        self.assertEqual(len(contents), 2)

        # Ask for parent folder
        contents = bucket_folder.parent.list_object_keys()
        self.assertIn(self.example1_key, contents)
        self.assertIn(self.example2_key, contents)
        self.assertEqual(len(contents), 4)

        # Use parents to get folder
        contents = bucket_folder.parents[-1].list_object_keys()
        self.assertIn(self.example1_key, contents)
        self.assertIn(self.example2_key, contents)
        self.assertEqual(len(contents), 4)

        root_folder = S3_Bucket_Folder(
            bucket_name=self.bucket1_name,
            folder='.',
            user_id='mock_user',
            raw_password='super secret password',
            password_source=PasswordSource.CONFIG_FILE,
        )
        folder1 = root_folder / 'folder1'
        contents = folder1.list_object_keys(key=None)
        self.assertNotIn(self.example1_key, contents)
        self.assertIn(self.example2_key, contents)
        self.assertEqual(len(contents), 2)

    def test_true_div(self):
        bucket = S3_Bucket(
            bucket_name=self.bucket1_name,
            user_id='mock_user',
            raw_password='super secret password',
            password_source=PasswordSource.CONFIG_FILE,
        )
        session = bucket.session

        folder_key = bucket / 'folder1'
        self.assertEqual("folder1", str(folder_key.key))
        self.assertEqual(bucket.bucket_name, folder_key.bucket_name)
        self.assertEqual(bucket.user_id, folder_key.user_id)
        self.assertEqual(bucket.get_password(), folder_key.get_password())
        self.assertTrue(folder_key.session is session)

        file_key = folder_key / 'file.txt'
        self.assertEqual("folder1/file.txt", str(file_key.key))
        self.assertEqual(bucket.bucket_name, file_key.bucket_name)
        self.assertEqual(bucket.user_id, file_key.user_id)
        self.assertEqual(bucket.get_password(), file_key.get_password())
        self.assertTrue(file_key.session is session)

    def test_nav_to_folder(self):
        bucket = S3_Bucket(
            bucket_name=self.bucket1_name,
            user_id='mock_user',
            raw_password='super secret password',
            password_source=PasswordSource.CONFIG_FILE,
        )
        session = bucket.session

        folder_key = bucket / 'folder1'
        self.assertEqual('folder1', str(folder_key.key))
        self.assertEqual(bucket.bucket_name, folder_key.bucket_name)
        self.assertEqual(bucket.user_id, folder_key.user_id)
        self.assertEqual(bucket.get_password(), folder_key.get_password())
        self.assertTrue(folder_key.session is session)

        folder_key2 = folder_key / 'folder2'
        self.assertEqual('folder1/folder2', folder_key2.key)
        self.assertEqual(bucket.bucket_name, folder_key2.bucket_name)
        self.assertEqual(bucket.user_id, folder_key2.user_id)
        self.assertEqual(bucket.get_password(), folder_key2.get_password())
        self.assertTrue(folder_key2.session is session)

        folder_key3 = folder_key / 'folder3'
        self.assertEqual("folder1/folder3", str(folder_key3.key))
        self.assertEqual(bucket.bucket_name, folder_key3.bucket_name)
        self.assertEqual(bucket.user_id, folder_key3.user_id)
        self.assertEqual(bucket.get_password(), folder_key3.get_password())
        self.assertTrue(folder_key3.session is session)

    def test_join_path(self):
        bucket = S3_Bucket(
            bucket_name=self.bucket1_name,
            user_id='mock_user',
            raw_password='super secret password',
            password_source=PasswordSource.CONFIG_FILE,
        )
        session = bucket.session

        folder_key = bucket.joinpath('folder1', 'folder2', 'file.txt')
        self.assertEqual("folder1/folder2/file.txt", str(folder_key.key))
        self.assertEqual(bucket.bucket_name, folder_key.bucket_name)
        self.assertEqual(bucket.user_id, folder_key.user_id)
        self.assertEqual(bucket.get_password(), folder_key.get_password())
        self.assertTrue(folder_key.session is session)

    def test_nav_to_file(self):
        bucket_folder = S3_Bucket_Folder(
            bucket_name=self.bucket1_name,
            folder='folder1',
            user_id='mock_user',
            raw_password='super secret password',
            password_source=PasswordSource.CONFIG_FILE,
        )
        session = bucket_folder.session

        bucket_file = bucket_folder / 'file.json'
        self.assertEqual(str(PurePosixPath('folder1') / "file.json"), str(bucket_file.key))
        self.assertEqual(bucket_folder.bucket_name, bucket_file.bucket_name)
        self.assertEqual(bucket_folder.user_id, bucket_file.user_id)
        self.assertEqual(bucket_folder.get_password(), bucket_file.get_password())
        self.assertTrue(bucket_file.session is session)

        bucket_key = bucket_folder / 'folder2'
        bucket_file2 = bucket_key / 'file.csv'
        self.assertEqual('folder1/folder2/file.csv', bucket_file2.key)
        self.assertEqual(bucket_folder.bucket_name, bucket_file2.bucket_name)
        self.assertEqual(bucket_folder.user_id, bucket_file2.user_id)
        self.assertEqual(bucket_folder.get_password(), bucket_file2.get_password())
        self.assertTrue(bucket_file2.session is session)

    def test_open(self):
        bucket = S3_Bucket(
            bucket_name=self.bucket1_name,
            user_id='mock_user',
            raw_password='super secret password',
            password_source=PasswordSource.CONFIG_FILE,
        )
        file1 = bucket / self.example1_key

        # Binary explicit
        with file1.open('rb') as bf:
            bf_contents = bf.read()
        with self.file1_path.open('rb') as lf:
            lf_contents = lf.read()
        self.assertEqual(lf_contents, bf_contents)

        # Text explicit
        with file1.open('rt', encoding='utf-8') as bf:
            bf_contents = bf.read()
        with self.file1_path.open('rt', encoding='utf-8') as lf:
            lf_contents = lf.read()
        self.assertEqual(lf_contents, bf_contents)

        # Text default and using readlines
        with file1.open('r', encoding='utf-8') as bf:
            bf_contents = bf.readlines()
        with self.file1_path.open('r', encoding='utf-8') as lf:
            lf_contents = lf.readlines()
        self.assertEqual(lf_contents, bf_contents)

    def _assert_files_equal(self, path1: Path, path2: Path):
        with path1.open('rb') as f1:
            with path2.open('rb') as f2:
                self.assertEqual(f1.read(), f2.read())

    def test_download(self):
        bucket = S3_Bucket(
            bucket_name=self.bucket1_name,
            user_id='mock_user',
            raw_password='super secret password',
            password_source=PasswordSource.CONFIG_FILE,
        )

        with TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            tmp_path = Path(tmp)
            tmp_file = tmp_path / 'path1'

            bucket.download_file(
                local_filename=tmp_file,
                key=str(self.example1_key),
            )
            self._assert_files_equal(self.file1_path, tmp_file)

            # Test default overwrite (OVERWRITE_OLDER)
            local_time_before = tmp_file.stat().st_mtime
            bucket.download_file(
                local_filename=tmp_file,
                key=str(self.example1_key),
            )
            local_time_after = tmp_file.stat().st_mtime
            self.assertEqual(
                local_time_before,
                local_time_after,
            )

            # Test if OVERWRITE_OLDER but it is not
            bucket.download_file(
                local_filename=tmp_file,
                key=str(self.example1_key),
                overwrite_mode=S3_Bucket.OverwriteModes.OVERWRITE_OLDER
            )
            local_time_after = tmp_file.stat().st_mtime
            self.assertEqual(
                local_time_before,
                local_time_after
            )

            # Make the local file appear older
            old_time = 946702800.0
            os.utime(tmp_file, (old_time, old_time))

            # Test do not overwrite
            test_overwrite_newer_s3 = 'do_not_overwrite.test'
            # upload a new file
            bucket.upload_file(
                local_filename=self.file1_path,
                key=test_overwrite_newer_s3
            )
            bucket.download_file(
                local_filename=tmp_file,
                key=test_overwrite_newer_s3,
                overwrite_mode=S3_Bucket.OverwriteModes.NEVER_OVERWRITE
            )
            local_time_after = tmp_file.stat().st_mtime
            self.assertEqual(
                old_time,
                local_time_after
            )

            # Test OVERWRITE_OLDER and local is older
            bucket.download_file(
                local_filename=tmp_file,
                key=test_overwrite_newer_s3,
                overwrite_mode=S3_Bucket.OverwriteModes.OVERWRITE_OLDER
            )
            local_time_after = tmp_file.stat().st_mtime
            self.assertLess(
                local_time_before,
                local_time_after
            )

            # Test ALWAYS_OVERWRITE
            bucket.download_file(
                local_filename=tmp_file,
                key=test_overwrite_newer_s3,
                overwrite_mode=S3_Bucket.OverwriteModes.ALWAYS_OVERWRITE
            )
            local_time_after_always = tmp_file.stat().st_mtime
            self.assertLess(
                local_time_after,
                local_time_after_always
            )

            tmp_file.unlink()
            bucket_file = bucket / self.example1_key
            bucket_file.download_file(local_filename=tmp_file)
            self._assert_files_equal(self.file1_path, tmp_file)

    def test_download_files_folder1(self):
        bucket = S3_Bucket(
            bucket_name=self.bucket1_name,
            user_id='mock_user',
            raw_password='super secret password',
            password_source=PasswordSource.CONFIG_FILE,
        )

        with TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            tmp_path = Path(tmp)
            download_path = tmp_path / 'sub'

            bucket.download_files(
                local_path=str(download_path),
                key='folder1',
            )
            self._assert_files_equal(self.file1_path, download_path / 'file.txt')
            self._assert_files_equal(self.file1_path, download_path / 'file2.txt')

    def test_download_files_prefix(self):
        bucket = S3_Bucket(
            bucket_name=self.bucket1_name,
            user_id='mock_user',
            raw_password='super secret password',
            password_source=PasswordSource.CONFIG_FILE,
        )

        with TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            tmp_path = Path(tmp)
            download_path = tmp_path / 'sub1'

            (bucket / 'folder').download_files(
                local_path=str(download_path),
            )
            self._assert_files_equal(self.file1_path, download_path / 'folder1' / 'file.txt')
            self._assert_files_equal(self.file1_path, download_path / 'folder1' / 'file2.txt')
            self._assert_files_equal(self.file2_path, download_path / 'folder2' / 'file3.txt')

    def test_download_files_root(self):
        bucket = S3_Bucket(
            bucket_name=self.bucket1_name,
            user_id='mock_user',
            raw_password='super secret password',
            password_source=PasswordSource.CONFIG_FILE,
        )

        with TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            tmp_path = Path(tmp)
            download_path = tmp_path / 'sub1'

            bucket.download_files(
                local_path=str(download_path),
            )
            self._assert_files_equal(self.file1_path, download_path / self.example1_key)
            self._assert_files_equal(self.file1_path, download_path / 'folder1' / 'file.txt')
            self._assert_files_equal(self.file1_path, download_path / 'folder1' / 'file2.txt')
            self._assert_files_equal(self.file2_path, download_path / 'folder2' / 'file3.txt')

    def test_bucket_upload(self):
        bucket = S3_Bucket(
            bucket_name=self.bucket1_name,
            user_id='mock_user',
            raw_password='super secret password',
            password_source=PasswordSource.CONFIG_FILE,
        )

        for key in [
            'uploaded_file.ini',
            'folder2/file2.ini',
        ]:
            bucket.upload_file(
                local_filename=self.file2_path,
                key=key,
            )

            contents = bucket.list_object_keys()
            self.assertIn(key, contents)

    def test_download_404_error(self):
        bucket = S3_Bucket(
            bucket_name=self.bucket1_name,
            user_id='mock_user',
            raw_password='super secret password',
            password_source=PasswordSource.CONFIG_FILE,
        )
        with self.assertRaises(ClientError) as raises_ex:
            bucket.download_file(key='this/file/does_not_exist', local_filename='test')

        print(raises_ex.exception.response)
        self.assertEqual(raises_ex.exception.response['Error']['Code'], "404")

    @set_initial_no_auth_action_count(0)
    def test_download_auth_error(self):
        bucket = S3_Bucket(
            bucket_name=self.bucket1_name,
            user_id='mock_user',
            raw_password='super secret password',
            password_source=PasswordSource.CONFIG_FILE,
        )
        with self.assertRaises(ClientError) as raises_ex:
            with TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
                tmp_path = Path(tmp)
                tmp_file = tmp_path / 'path1'

                bucket.download_file(
                    local_filename=tmp_file,
                    key=str(self.example1_key),
                )
        print(raises_ex.exception.response)
        self.assertEqual(raises_ex.exception.response['Error']['Code'], "InvalidAccessKeyId")
