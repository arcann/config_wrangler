import unittest

import boto3
import moto

from config_wrangler.config_templates.credentials import PasswordSource
from config_wrangler.config_templates.aws.s3_bucket import S3_Bucket, S3_Bucket_Folder
from tests.base_tests_mixin import Base_Tests_Mixin


@moto.mock_s3
class TestS3HelperFunctions(unittest.TestCase, Base_Tests_Mixin):
    def setUp(self):
        self.mock_client = boto3.client('s3')
        self.bucket1_name = 'mock_bucket'
        self.mock_client.create_bucket(
            Bucket=self.bucket1_name,
            ACL='private',
        )
        self.bucket2_name = 'mock_bucket2'
        self.mock_client.create_bucket(
            Bucket=self.bucket2_name,
        )

        self.bucket3_name = 'mock_bucket3'
        self.mock_client.create_bucket(
            Bucket=self.bucket3_name,
        )

        self.example1_key = 'test_good.ini'
        self.mock_client.upload_file(
            Bucket=self.bucket1_name,
            Key=self.example1_key,
            Filename=str(self.get_test_files_path() / 'test_good.ini')
        )
        self.example2_key = 'folder1/file.txt'
        self.mock_client.upload_file(
            Bucket=self.bucket1_name,
            Key=self.example2_key,
            Filename=str(self.get_test_files_path() / 'test_good.ini')
        )

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
        self.assertEqual(len(contents), 2)

        bucket2 = S3_Bucket(
            bucket_name=self.bucket2_name,
            user_id='mock_user',
            raw_password='super secret password',
            password_source=PasswordSource.CONFIG_FILE,
        )
        contents = bucket2.list_object_keys(key=None)
        self.assertNotIn(self.example1_key, contents)
        self.assertEqual(len(contents), 0)

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
        self.assertEqual(len(contents), 1)

        # Ask for a different folder
        contents = bucket_folder.list_object_keys(key='')
        self.assertIn(self.example1_key, contents)
        self.assertIn(self.example2_key, contents)
        self.assertEqual(len(contents), 2)

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
        self.assertEqual(len(contents), 1)

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

        folder_key = bucket.nav_to_folder('folder1')
        self.assertEqual("folder1", str(folder_key.folder))
        self.assertEqual(bucket.bucket_name, folder_key.bucket_name)
        self.assertEqual(bucket.user_id, folder_key.user_id)
        self.assertEqual(bucket.get_password(), folder_key.get_password())
        self.assertTrue(folder_key.session is session)

        folder_key2 = folder_key.nav_to_folder('folder2')
        self.assertEqual("folder2", str(folder_key2.folder))
        self.assertEqual(bucket.bucket_name, folder_key2.bucket_name)
        self.assertEqual(bucket.user_id, folder_key2.user_id)
        self.assertEqual(bucket.get_password(), folder_key2.get_password())
        self.assertTrue(folder_key2.session is session)

        folder_key3 = folder_key.nav_to_relative_folder('folder3')
        self.assertEqual("folder1/folder3", str(folder_key3.folder))
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

        bucket_file = bucket_folder.nav_to_file('file.json')
        self.assertEqual("file.json", str(bucket_file.file_name))
        self.assertEqual(bucket_folder.folder, str(bucket_file.folder))
        self.assertEqual(bucket_folder.bucket_name, bucket_file.bucket_name)
        self.assertEqual(bucket_folder.user_id, bucket_file.user_id)
        self.assertEqual(bucket_folder.get_password(), bucket_file.get_password())
        self.assertTrue(bucket_file.session is session)

        bucket_key = bucket_folder / 'folder2'
        bucket_file2 = bucket_key.nav_to_file('file.csv')
        self.assertEqual("file.csv", str(bucket_file2.file_name))
        self.assertEqual(bucket_key.key, str(bucket_file2.folder))
        self.assertEqual(bucket_folder.bucket_name, bucket_file2.bucket_name)
        self.assertEqual(bucket_folder.user_id, bucket_file2.user_id)
        self.assertEqual(bucket_folder.get_password(), bucket_file2.get_password())
        self.assertTrue(bucket_file2.session is session)

    def test_bucket_upload(self):
        pass
