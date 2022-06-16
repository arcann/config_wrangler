import unittest

import boto3
import moto

from config_wrangler.config_templates.credentials import PasswordSource
from config_wrangler.config_templates.s3_bucket import S3_Bucket, S3_Bucket_Folder
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

    def test_bucket_upload(self):
        pass
