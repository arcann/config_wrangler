import logging
import os
import unittest

import boto3
from moto import mock_aws
from mypy_boto3_ssm.client import SSMClient

from config_wrangler.config_templates.aws.ssm import SSM
from config_wrangler.config_templates.credentials import PasswordSource
from tests.base_tests_mixin import Base_Tests_Mixin


@mock_aws
class TestSSM(unittest.TestCase, Base_Tests_Mixin):
    def setUp(self):
        logging.basicConfig(level=logging.INFO)
        self.region = 'us-east-2'
        self.mock_client: SSMClient = boto3.client('ssm', region_name=self.region)

        self.parameter1 = 'my_parameters/parameter-1'
        self.parameter1_value = "8223"
        self.mock_client.put_parameter(
            Name=self.parameter1,
            Value=self.parameter1_value,
            Type="String",
        )

        self.parameter2 = 'other-parameter-2'
        self.parameter2_value = "lorum ipsum"
        self.mock_client.put_parameter(
            Name=self.parameter2,
            Value=self.parameter2_value,
            Type="SecureString",
        )

        self.parameter3 = 'my_parameters/list_param'
        self.parameter3_value = "apple, banana"
        self.mock_client.put_parameter(
            Name=self.parameter3,
            Value=self.parameter3_value,
            Type="StringList",
        )

    def test_get1(self):
        os.environ['password_mock_user'] = 'super secret password'
        ssm = SSM(
            user_id='mock_user',
            password_source=PasswordSource.ENVIRONMENT,
            region_name=self.region,
        )
        value = ssm.get_parameter_value(self.parameter1)
        self.assertEqual(self.parameter1_value, value)

        value2 = ssm.get_parameter_value(self.parameter2)
        self.assertEqual(self.parameter2_value, value2)

        value3 = ssm.get_parameter_value(self.parameter3)
        self.assertEqual(self.parameter3_value, value3)

        value2_enc = ssm.get_parameter_value(self.parameter2, with_decryption=False)
        self.assertNotEqual(self.parameter2_value, value2_enc)
        # The value comes out of moto as 'kms:alias/aws/ssm:lorum ipsum' but can we rely on that?

    def test_get_list(self):
        os.environ['password_mock_user'] = 'super secret password'
        ssm = SSM(
            user_id='mock_user',
            password_source=PasswordSource.ENVIRONMENT,
            region_name=self.region,
        )
        param_dict = ssm.get_parameters(
            names=[self.parameter1, self.parameter2]
        )
        self.assertEqual(2, len(param_dict))
        self.assertEqual(self.parameter1_value, param_dict[self.parameter1])
        self.assertEqual(self.parameter2_value, param_dict[self.parameter2])

    def test_get_path(self):
        os.environ['password_mock_user'] = 'super secret password'
        ssm = SSM(
            user_id='mock_user',
            password_source=PasswordSource.ENVIRONMENT,
            region_name=self.region,
        )
        param_dict = ssm.get_parameters_by_path(
            path='my_parameters'
        )
        self.assertEqual(2, len(param_dict))
        self.assertEqual(self.parameter1_value, param_dict[self.parameter1])
        self.assertEqual(self.parameter3_value, param_dict[self.parameter3])

    def test_get_path_root(self):
        os.environ['password_mock_user'] = 'super secret password'
        ssm = SSM(
            user_id='mock_user',
            password_source=PasswordSource.ENVIRONMENT,
            region_name=self.region,
        )
        param_dict = ssm.get_parameters_by_path(
            path='/',
        )
        self.assertEqual(3, len(param_dict))
        self.assertEqual(self.parameter1_value, param_dict[self.parameter1])
        self.assertEqual(self.parameter2_value, param_dict[self.parameter2])
        self.assertEqual(self.parameter3_value, param_dict[self.parameter3])
