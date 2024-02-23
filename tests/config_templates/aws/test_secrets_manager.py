import logging
import os
import unittest

import boto3
from botocore.exceptions import ClientError
from moto import mock_aws
from mypy_boto3_secretsmanager.client import SecretsManagerClient

from config_wrangler.config_templates.aws.secrets_manager import SecretsManager
from config_wrangler.config_templates.credentials import PasswordSource
from tests.base_tests_mixin import Base_Tests_Mixin


@mock_aws
class TestSecretsManager(unittest.TestCase, Base_Tests_Mixin):
    def setUp(self):
        logging.basicConfig(level=logging.INFO)
        self.region = 'us-west-1'
        self.mock_client: SecretsManagerClient = boto3.client('secretsmanager', region_name=self.region)

        self.secret1_name = 'secret_id_1'
        self.secret1_value = "one super secret value"
        response = self.mock_client.create_secret(
            Name=self.secret1_name,
            SecretString=self.secret1_value,
        )
        self.secret1_id = response['ARN']

        # self.mock_client.put_secret_value(
        #     SecretId=self.secret1_id,
        #     SecretString=self.secret1_newvalue,
        # )

        self.secret2_name = 'binary_secret_id_2'
        self.secret2_value = b"very secret bytes"
        response = self.mock_client.create_secret(
            Name=self.secret2_name,
            SecretBinary=self.secret2_value,
        )
        self.secret2_id = response['ARN']

    def test_get1(self):
        os.environ['password_mock_user'] = 'super secret password'
        sm = SecretsManager(
            user_id='mock_user',
            password_source=PasswordSource.ENVIRONMENT,
            region_name=self.region,
        )
        value = sm.get_secret_value_by_id(self.secret1_id)
        self.assertEqual(self.secret1_value, value)

        with self.assertRaises(ValueError):
            _ = sm.get_secret_value_bytes_by_id(self.secret1_id)

    def test_get2(self):
        os.environ['password_mock_user'] = 'super secret password'
        sm = SecretsManager(
            user_id='mock_user',
            password_source=PasswordSource.ENVIRONMENT,
            region_name=self.region,
        )
        value = sm.get_secret_value_bytes_by_id(self.secret2_id)
        self.assertEqual(self.secret2_value, value)

        with self.assertRaises(ValueError):
            _ = sm.get_secret_value_by_id(self.secret2_id)

    def test_get_bad(self):
        os.environ['password_mock_user'] = 'super secret password'
        sm = SecretsManager(
            user_id='mock_user',
            password_source=PasswordSource.ENVIRONMENT,
            region_name=self.region,
        )
        with self.assertRaises(ClientError):
            _ = sm.get_secret_value_bytes_by_id('bad_secret_id')

        with self.assertRaises(ClientError):
            _ = sm.get_secret_value_by_id('bad_secret_id')
