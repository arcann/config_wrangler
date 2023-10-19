import unittest

import boto3
import moto

from config_wrangler.config_templates.sqlalchemy_database import SQLAlchemyDatabase
from tests.base_tests_mixin import Base_Tests_Mixin


@moto.mock_redshift
class TestSQLAlchemyDatabase(unittest.TestCase, Base_Tests_Mixin):
    def setUp(self):
        client = boto3.client("redshift", region_name="us-east-1")
        self.cluster_identifier = 'mock_cluster'
        client.create_cluster(
            ClusterIdentifier=self.cluster_identifier,
            ClusterType="single-node",
            DBName="db_1",
            MasterUsername="user",
            MasterUserPassword="password",
            NodeType="ds2.xlarge",
        )

    def test_redshift_uri_cluster_creds(self):
        config = SQLAlchemyDatabase(
            dialect='redshift+psycopg2',
            use_get_cluster_credentials=True,
            host='mock.us-east-1.redshift.amazonaws.com',
            database_name='db_1',
            rs_region_name='us-east-1',
            rs_cluster_id=self.cluster_identifier,
            rs_db_user_id='mock_user',
            password_source='CONFIG_FILE',
            user_id='my_access_key',
            raw_password='my_secret_key',
        )
        access_key = config.get_password()
        self.assertEqual(access_key, 'my_secret_key')
        uri = config.get_uri()
        self.assertEqual(uri.database, 'db_1')
        self.assertEqual(uri.drivername, 'redshift+psycopg2')
        self.assertEqual(uri.host, 'mock.us-east-1.redshift.amazonaws.com')
        # Not equal because use_get_cluster_credentials should have caused it to change
        self.assertNotEqual(uri.username, 'my_access_key')
        self.assertNotEqual(uri.password, 'my_secret_key')
        uri2 = config.get_uri()
        # Each call with use_get_cluster_credentials should get a unique password
        self.assertNotEqual(uri.password, uri2.password)

    def test_redshift_uri_cluster_creds_with_groups(self):
        config = SQLAlchemyDatabase(
            dialect='redshift+psycopg2',
            use_get_cluster_credentials=True,
            host='mock.us-east-1.redshift.amazonaws.com',
            database_name='db_1',
            rs_region_name='us-east-1',
            rs_cluster_id=self.cluster_identifier,
            rs_auto_create=True,
            rs_db_user_id='mock_user',
            rs_db_groups=['group1', 'group2'],
            password_source='CONFIG_FILE',
            user_id='my_access_key',
            raw_password='my_secret_key',
        )
        access_key = config.get_password()
        self.assertEqual(access_key, 'my_secret_key')
        uri = config.get_uri()
        self.assertEqual(uri.database, 'db_1')
        self.assertEqual(uri.drivername, 'redshift+psycopg2')
        self.assertEqual(uri.host, 'mock.us-east-1.redshift.amazonaws.com')
        # Not equal because use_get_cluster_credentials should have caused it to change
        self.assertNotEqual(uri.username, 'my_access_key')
        self.assertNotEqual(uri.password, 'my_secret_key')
        uri2 = config.get_uri()
        # Each call with use_get_cluster_credentials should get a unique password
        self.assertNotEqual(uri.password, uri2.password)

    def test_redshift_uri_db_creds(self):
        config = SQLAlchemyDatabase(
            dialect='redshift+psycopg2',
            use_get_cluster_credentials=False,
            host='mock.us-east-1.redshift.amazonaws.com',
            database_name='db_1',
            rs_region_name='us-east-1',
            rs_cluster_id=self.cluster_identifier,
            password_source='CONFIG_FILE',
            user_id='db_user_id',
            raw_password='my_password',
        )
        access_key = config.get_password()
        self.assertEqual(access_key, 'my_password')
        uri = config.get_uri()
        self.assertEqual(uri.database, 'db_1')
        self.assertEqual(uri.drivername, 'redshift+psycopg2')
        self.assertEqual(uri.host, 'mock.us-east-1.redshift.amazonaws.com')
        # Not equal because use_get_cluster_credentials should have caused it to change
        self.assertEqual(uri.username, 'db_user_id')
        self.assertEqual(uri.password, 'my_password')
        uri2 = config.get_uri()
        self.assertEqual(uri.password, uri2.password)
        self.assertEqual(uri.username, uri2.username)
