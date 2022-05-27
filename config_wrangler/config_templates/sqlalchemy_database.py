import logging
from typing import *
from datetime import datetime, timedelta, timezone

from pydantic import PrivateAttr, root_validator


try:
    # noinspection PyPackageRequirements
    from sqlalchemy.engine import Engine
    # noinspection PyPackageRequirements
    from sqlalchemy.sql.schema import DEFAULT_NAMING_CONVENTION
    # noinspection PyPackageRequirements
    from sqlalchemy import create_engine, event, MetaData
    # noinspection PyPackageRequirements
    from sqlalchemy.engine.url import URL
    # noinspection PyPackageRequirements
    from sqlalchemy.orm import Session
    # noinspection PyPackageRequirements
    from sqlalchemy.pool import QueuePool, NullPool
    # noinspection PyPackageRequirements
    from sqlalchemy.exc import SQLAlchemyError
except ImportError:
    raise ImportError("SQLAlchemyDatabase requires sqlalchemy to be installed")

from config_wrangler.config_templates.credentials import Credentials


class SQLAlchemyDatabase(Credentials):
    dialect: str
    driver: str = None
    host: str
    port: int = None
    database_name: str
    use_get_cluster_credentials: bool = False
    rs_new_credentials_seconds: int = 1800
    rs_region_name: str = None
    rs_cluster_id: str = None
    aws_access_key_id: str = None
    aws_secret_access_key: str = None
    rs_db_user_id: str = None
    rs_duration_seconds: str = 3600
    create_engine_args: Dict[str, Any] = {}
    arraysize: int = 5000  # Only used for Oracle
    encoding: str = None
    poolclass: str = None

    # Private attribute used to hold the redshift client
    _engine = PrivateAttr(default=None)
    _sqlite_connection = PrivateAttr(default=None)
    _rs_client = PrivateAttr(default=None)
    _rs_credential_expiry: datetime = PrivateAttr(default=None)

    # Values to hide from config exports
    _private_value_atts = PrivateAttr(default={'password', 'aws_secret_access_key'})

    def __repr__(self):
        return f"SQLAlchemyDatabase({self.get_uri()})"

    def __str__(self):
        return str(self.get_uri())

    @root_validator(pre=True)
    def translate(cls, values):
        # Convert from old setting names to new names
        name_map = {
            'dsn': 'host',
            'dbname': 'database_name',
            'key_ring_system': 'keyring_section',
            'default_user_id': 'user_id',
        }
        for old, new in name_map.items():
            if old in values and new not in values:
                values[new] = values[old]
                del values[old]

        if values.get('dialect') in {'sqlite'}:
            values['user_id'] = 'NA'
            values['host'] = 'NA'

        if 'create_engine_args' in values:
            create_engine_args = values['create_engine_args']
            if not isinstance(create_engine_args, dict):
                create_engine_args_dict = dict()
                for arg in create_engine_args.split('\n'):
                    arg = arg.strip()
                    if arg != '':
                        arg_name, arg_value = arg.split('=')
                        arg_name = arg_name.strip()
                        arg_value = arg_value.strip()
                        try:
                            arg_value_int = int(arg_value)
                            arg_value = arg_value_int
                        except ValueError:
                            pass
                        create_engine_args_dict[arg_name] = arg_value
                values['create_engine_args'] = create_engine_args_dict

        return values

    def get_password(self) -> str:
        try:
            return super().get_password()
        except ValueError:
            if self.dialect not in {'sqlite'}:
                raise
            else:
                # noinspection PyTypeChecker
                return None

    @staticmethod
    def _now():
        return datetime.now(timezone.utc)

    def get_cluster_credentials(self) -> Tuple[str, str]:
        if self._rs_client is None:
            import boto3

            self._rs_client = boto3.client(
                'redshift',
                region_name=self.rs_region_name,
                aws_access_key_id=self.aws_access_key_id,
                aws_secret_access_key=self.aws_secret_access_key,
                aws_session_token=None,
            )
        new_credentials = self._rs_client.get_cluster_credentials(
                DbUser=self.rs_db_user_id,
                DbName=self.database_name,
                DurationSeconds=self.rs_duration_seconds,
                ClusterIdentifier=self.rs_cluster_id
            )
        rs_new_credentials_timedelta = timedelta(seconds=self.rs_new_credentials_seconds)
        self._rs_credential_expiry = self._now() + rs_new_credentials_timedelta
        if 'DbUser' not in new_credentials or 'DbPassword' not in new_credentials:
            raise SQLAlchemyError(f'Invalid response from get_cluster_credentials got {new_credentials}')
        if 'Expiration' in new_credentials:
            # Expire when redshift said or sooner as specified by rs_new_credentials_seconds
            server_expiry = new_credentials['Expiration']
            if server_expiry.tzinfo is None:
                # Moto seems to return naive datetime in local tz.
                # Boto3 returns tz aware datetime
                server_expiry = server_expiry.astimezone(tz=None)
            self._rs_credential_expiry = min(self._rs_credential_expiry, server_expiry)

        return new_credentials['DbUser'], new_credentials['DbPassword']

    def _get_connector(self) -> str:
        if self.driver is None:
            return self.dialect
        else:
            return f"{self.dialect}+{self.driver}"

    def get_uri(self) -> URL:
        user_id = self.user_id
        password = self.get_password()
        if self.use_get_cluster_credentials:
            if self.aws_access_key_id is None:
                self.aws_access_key_id = self.user_id
            if self.aws_secret_access_key is None:
                self.aws_secret_access_key = password

            if self.rs_db_user_id is None:
                raise ValueError(
                    f'rs_db_user_id required for {self.__class__.__name__} {self.host} '
                    f'with use_get_cluster_credentials = True.'
                )

            user_id, password = self.get_cluster_credentials()

        if self.dialect in {'sqlite'}:
            # noinspection PyTypeChecker
            self.host = None
            # noinspection PyTypeChecker
            self.user_id = None

        return URL(
            drivername=self._get_connector(),
            host=self.host,
            port=self.port,
            username=user_id,
            password=password,
            database=self.database_name,
        )

    def get_engine(self) -> Engine:
        if self._engine is None:

            kwargs = self.create_engine_args or {}
            if self.dialect == 'oracle':
                if 'arraysize' not in kwargs:
                    kwargs['arraysize'] = self.arraysize
            if self.encoding:
                kwargs['encoding'] = self.encoding
            if self.poolclass:
                if self.poolclass == 'QueuePool':
                    kwargs['poolclass'] = QueuePool
                elif self.poolclass == 'NullPool':
                    kwargs['poolclass'] = NullPool
                else:
                    raise ValueError(f'Unexpected poolclass {self.poolclass}')

            self._engine = create_engine(self.get_uri(), **kwargs)

            # Make an event listener so we can get new RS credentials if needed
            @event.listens_for(self._engine, 'do_connect', named=True)
            def engine_do_connect(**kw):
                """
                listen for the 'do_connect' event
                """
                # from bi_etl.utility import dict_to_str
                # print(dict_to_str(kw))
                if self.use_get_cluster_credentials:
                    if self._now() >= self._rs_credential_expiry:
                        logging.info('Getting new Redshift cluster credentials')
                        db_user, password = self.get_cluster_credentials()
                        kw['cparams']['user'] = db_user
                        kw['cparams']['password'] = password

                # Return None to allow control to pass to the next event handler and ultimately
                # to allow the dialect to connect normally, given the updated arguments.
                return None
            # End engine_do_connect sub function

        return self._engine

    def raw_connection(self):
        return self.get_engine().raw_connection()

    def connect(self):
        if self.dialect == 'sqlite':
            if self._sqlite_connection is None or self._sqlite_connection.closed:
                self._sqlite_connection = self.get_engine().connect()
            return self._sqlite_connection
        else:
            return self.get_engine().connect()

    def session(self, autocommit: bool = False) -> Session:
        return Session(bind=self.get_engine(), autocommit=autocommit)


class SQLAlchemyMetadata(SQLAlchemyDatabase):
    # Note: we can't name this field schema since that conflicts with pydantic
    database_schema: str = None
    quote_schema: str = None
    naming_convention: dict = DEFAULT_NAMING_CONVENTION

    def get_metadata(
            self,
    ) -> MetaData:
        engine = self.get_engine()
        return MetaData(
            bind=engine,
            schema=self.database_schema,
            quote_schema=self.quote_schema
        )
