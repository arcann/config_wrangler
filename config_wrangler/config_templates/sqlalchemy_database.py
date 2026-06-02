import logging
import warnings
from typing import *
from datetime import datetime, timedelta, timezone

from pydantic import model_validator, PrivateAttr

from config_wrangler.config_templates.aws.aws_session import AWS_Session

try:
    # noinspection PyPackageRequirements
    from sqlalchemy.engine import Engine, ExceptionContext
    # noinspection PyPackageRequirements
    from sqlalchemy.sql.schema import DEFAULT_NAMING_CONVENTION
    # noinspection PyPackageRequirements
    from sqlalchemy import create_engine, event, MetaData, select
    # noinspection PyPackageRequirements
    from sqlalchemy.engine.url import URL
    # noinspection PyPackageRequirements
    from sqlalchemy.orm import Session
    # noinspection PyPackageRequirements
    from sqlalchemy.pool import QueuePool, NullPool
    # noinspection PyPackageRequirements
    from sqlalchemy.exc import SQLAlchemyError, DBAPIError, DisconnectionError
except ImportError:
    raise ImportError("SQLAlchemyDatabase requires sqlalchemy to be installed")

from config_wrangler.config_templates.credentials import Credentials
from config_wrangler.config_templates.password_source import PasswordSource

if TYPE_CHECKING:
    from mypy_boto3_redshift.client import RedshiftClient


class SQLAlchemyDatabase(Credentials):
    dialect: str
    """
    The SQLAlchemy dialect to use.  See https://docs.sqlalchemy.org/en/20/dialects/
    """

    driver: Optional[str] = None
    """
    The python database driver to use. 
    This is optional in the SQLAlchemy connection string it would be the optional +driver value
    that can come after the dialect name.
    
    For example:
    
    .. code-block:: ini
    
        dialect=postgresql
        driver=psycopg2
        
    Would generate a connection string like:
    
    .. code-block:: text
    
        postgresql+psycopg2://user:password@host:port/dbname
        
    You could also provide both dialect and driver in the dialect field like this:
    
    .. code-block:: ini
    
        dialect=postgresql+psycopg2                        
    """

    host: Optional[str] = None
    """
    Hostname or IP number. May also be a data source name for some drivers.
    https://docs.sqlalchemy.org/en/20/core/engines.html#sqlalchemy.engine.URL.host
    """

    port: Optional[int] = None
    """
    Integer port number.
    https://docs.sqlalchemy.org/en/20/core/engines.html#sqlalchemy.engine.URL.port
    """

    database_name: str
    """
    https://docs.sqlalchemy.org/en/20/core/engines.html#sqlalchemy.engine.URL.database
    """

    use_get_cluster_credentials: bool = False
    """
    For Amazon Redshift only.  Should the boto3 call be performed to get temporary 
    database credentials?  If so, then rs_db_user_id is required.
    """

    rs_new_credentials_seconds: int = 1800
    """
    For Amazon Redshift and with use_get_cluster_credentials = True only.
    How long should we wait before requesting new temporary credentials last (in seconds).
    This should be less than the value used in rs_duration_seconds.
    Note: The server might respond with an even shorter duration, if so that will be used.  
    """

    rs_duration_seconds: Optional[int] = 3600
    """
    For Amazon Redshift and with use_get_cluster_credentials = True only.
    The value here is passed to the boto3 get_cluster_credentials call.   
    """

    rs_region_name: Optional[str] = None
    """
    For Amazon Redshift only. The region_name to use.
    """

    rs_cluster_id: Optional[str] = None
    """
    For Amazon Redshift only. The cluster name to use.
    """

    rs_auto_create: Optional[bool] = None
    """
    For Amazon Redshift and with use_get_cluster_credentials = True only.
    The value here is passed to the boto3 get_cluster_credentials call.   
    """

    rs_db_groups: Optional[List[str]] = None
    """
    For Amazon Redshift and with use_get_cluster_credentials = True only.
    The value here is passed to the boto3 get_cluster_credentials call.   
    """

    aws_access_key_id: Optional[str] = None
    """
    For Amazon Redshift and with use_get_cluster_credentials = True only.
    If provided, use this access key to authenticate for the use_get_cluster_credentials call.
    If not provided, the user_id value will be used instead.   
    """

    aws_secret_access_key: Optional[str] = None
    """
    For Amazon Redshift and with use_get_cluster_credentials = True only.
    If provided, use this access key to authenticate for the use_get_cluster_credentials call.
    If not provided, get_password() will be used to get the password from the configured 
    password source (see `PasswordSource` for options.)   
    """

    rs_db_user_id: Optional[str] = None
    """
    For Amazon Redshift and with use_get_cluster_credentials = True only.
    The value here is passed to the boto3 get_cluster_credentials call.   
    """

    create_engine_args: Dict[str, Any] = {}
    """
    A dictionary with extra arguments to pass to the SQLAlchemy create_engine function.
    See
    https://docs.sqlalchemy.org/en/20/core/engines.html#sqlalchemy.create_engine    
    """

    dbapi_args: Dict[str, Any] = {}
    """
    A dictionary with extra arguments to pass to the DBAPI via SQLAlchemy URI query parameters
    See
    https://docs.sqlalchemy.org/en/20/core/engines.html#sqlalchemy.engine.URL.query    
    """

    arraysize: Optional[int] = 5000
    """
    Only used for Oracle. Passed to SQLAlchemy create_engine function.
    """

    encoding: Optional[str] = None
    """
    Passed to SQLAlchemy create_engine function.
    """

    poolclass: Optional[str] = None
    """
    Pool subclass that should be passed to SQLAlchemy create_engine function.
    Only supports None, QueuePool or NullPool.
    See
    https://docs.sqlalchemy.org/en/20/core/engines.html#sqlalchemy.create_engine.params.poolclass
    """

    # Private attribute used to hold the engine
    _engine: 'Engine' = PrivateAttr(default=None)
    # noinspection PyUnresolvedReferences
    _sqlite_connection: 'sqlalchemy.engine.base.Connection' = PrivateAttr(default=None)
    # Private attribute used to hold the redshift client
    _rs_client: 'RedshiftClient' = PrivateAttr(default=None)
    _rs_credential_expiry: datetime = PrivateAttr(default=None)
    _rs_session: AWS_Session = PrivateAttr(default=None)

    # Values to hide from config exports
    _private_value_atts: set[str] = PrivateAttr(default={'password', 'aws_secret_access_key'})

    def __repr__(self):
        return Credentials.__repr__(self)

    def __str__(self):
        return str(self.get_uri())

    # Note the order of decorators matters!
    # noinspection PyNestedDecorators
    @model_validator(mode="before")
    @classmethod
    def translate(cls, values):
        if not isinstance(values, dict):
            raise ValueError(f"translate values: {values} must be a dict not {type(values)}")

        # Convert from old setting names to new names
        name_map = {
            'dsn': 'host',
            'dbname': 'database_name',
            'key_ring_system': 'keyring_section',
            'default_user_id': 'user_id',
        }
        for old, new in name_map.items():
            if old in values and new not in values:
                warnings.warn(f"Config SQLAlchemyDatabase.{old} is deprecated. Use {new} instead.")
                values[new] = values[old]
                del values[old]

        if values.get('dialect') in {'sqlite'}:
            values['user_id'] = 'NA'
            values['host'] = 'NA'
        else:
            if values.get('host', None) is None:
                raise ValueError("host is required for databases other than sqlite")

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

    @model_validator(mode='after')
    def check_model(self):
        if self.dialect == 'sqlite':
            # Bypass password checks
            return self
        else:
            if self.use_get_cluster_credentials:
                if self.rs_cluster_id is None:
                    raise ValueError("rs_cluster_id required when use_get_cluster_credentials is True")
            # noinspection PyCallingNonCallable
            return Credentials.check_model(self)

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
        log = logging.getLogger('get_cluster_credentials')
        if self._rs_client is None:
            import boto3

            if self.password_source == PasswordSource.AWS_ASSUME_ROLE:
                from config_wrangler.config_templates.aws.aws_session import AWS_Session
                self._rs_session = AWS_Session(
                    region_name=self.rs_region_name,
                    password_source=self.password_source,
                )
                self._rs_client = self._rs_session.session.client(
                    'redshift',
                    region_name=self.rs_region_name,
                )
            else:
                self._rs_client = boto3.client(
                    'redshift',
                    region_name=self.rs_region_name,
                    aws_access_key_id=self.aws_access_key_id,
                    aws_secret_access_key=self.aws_secret_access_key,
                    aws_session_token=None,
                )

        # Send optional params to get_cluster_credentials only if they have real values
        extra_get_cluster_credentials_args = dict()
        if self.rs_auto_create is not None:
            extra_get_cluster_credentials_args['AutoCreate'] = self.rs_auto_create

        if self.rs_db_groups is not None:
            extra_get_cluster_credentials_args['DbGroups'] = self.rs_db_groups

        assert self.rs_db_user_id is not None
        assert self.rs_duration_seconds is not None
        assert self.rs_cluster_id is not None

        new_credentials = self._rs_client.get_cluster_credentials(
            DbUser=self.rs_db_user_id,
            DbName=self.database_name,
            DurationSeconds=self.rs_duration_seconds,
            ClusterIdentifier=self.rs_cluster_id,
            **extra_get_cluster_credentials_args
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
            expire_in_seconds = (server_expiry - self._now()).total_seconds()
            log.debug(
                f'Got credentials that expire in {expire_in_seconds} seconds '
                f'at {server_expiry}'
            )
            safe_expire_in_seconds = max(expire_in_seconds - (15*60), 1)
            safe_credential_expiry = self._now() + timedelta(seconds=safe_expire_in_seconds)

            if safe_credential_expiry < self._rs_credential_expiry:
                self._rs_credential_expiry = safe_credential_expiry
                log.debug(
                    f'Using available lifetime minus up to 15 minutes. Will get new credentials in {safe_expire_in_seconds} seconds '
                    f'at {self._rs_credential_expiry}'
                )
        else:
            log.warning(
                'AWS did not specify Expiration. '
                f'Will use config setting of {self.rs_new_credentials_seconds} seconds. '
                f'Expire at {self._rs_credential_expiry}'
            )
        if self._rs_session is not None:
            iam_expiry = self._rs_session.get_session_expiry()
            log.debug(f"IAM expiry = {iam_expiry}")
            if iam_expiry < self._rs_credential_expiry:
                self._rs_credential_expiry = iam_expiry
                log.debug(f"IAM credentials expire sooner. Using that value = {iam_expiry}")

        return new_credentials['DbUser'], new_credentials['DbPassword']

    def _get_connector(self) -> str:
        if self.driver is None:
            return self.dialect
        else:
            return f"{self.dialect}+{self.driver}"

    def get_uri(self) -> URL:
        user_id = self.user_id
        if self.use_get_cluster_credentials:
            if self.password_source != PasswordSource.AWS_ASSUME_ROLE:
                if self.aws_access_key_id is None:
                    self.aws_access_key_id = self.user_id
                if self.aws_secret_access_key is None:
                    self.aws_secret_access_key = self.get_password()

            if self.rs_db_user_id is None:
                raise ValueError(
                    f'rs_db_user_id required for {self.__class__.__name__} {self.host} '
                    f'with use_get_cluster_credentials = True.'
                )

            user_id, password = self.get_cluster_credentials()
        else:
            # Will be set below
            password = None

        if self.dialect in {'sqlite'}:
            return URL.create(
                drivername=self._get_connector(),
                database=self.database_name,
                query=self.dbapi_args,
            )
        else:
            if not self.use_get_cluster_credentials:
                password = self.get_password()

            try:
                return URL.create(
                    drivername=self._get_connector(),
                    host=self.host,
                    port=self.port,
                    username=user_id,
                    password=password,
                    database=self.database_name,
                    query=self.dbapi_args,
                )
            except AttributeError:
                # noinspection PyTypeChecker
                return URL(
                    drivername=self._get_connector(),
                    host=self.host,
                    port=self.port,
                    username=user_id,
                    password=password,
                    database=self.database_name,
                    query=self.dbapi_args,
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
                    raise ValueError(
                        f'Unexpected poolclass {self.poolclass}. '
                        f'Valid choices: QueuePool or NullPool.'
                    )

            self._engine = create_engine(self.get_uri(), **kwargs)

            if self.use_get_cluster_credentials:
                log = logging.getLogger('get_cluster_credentials')

                # Make an event listener, so we can get new RS credentials if needed
                @event.listens_for(self._engine, 'do_connect', named=True)
                def engine_do_connect(**kw):
                    """
                    listen for the 'do_connect' event
                    """
                    # from bi_etl.utility import dict_to_str
                    # print(dict_to_str(kw))
                    if self._now() >= self._rs_credential_expiry:
                        log.debug(
                            f'connect: Calling Redshift get_cluster_credentials since it is after {self._rs_credential_expiry}'
                        )
                        db_user, password = self.get_cluster_credentials()
                        kw['cparams']['user'] = db_user
                        kw['cparams']['password'] = password
                    else:
                        log.debug(
                            f'connect: Creds still valid. Good until {self._rs_credential_expiry}'
                        )

                    # Return None to allow control to pass to the next event handler and ultimately
                    # to allow the dialect to connect normally, given the updated arguments.
                    return None
                # End engine_do_connect sub function

                @event.listens_for(self._engine, 'checkout')
                def receive_checkout(dbapi_connection, connection_record, connection_proxy):
                    """
                    listen for the 'checkout' event
                    """
                    if self._now() >= self._rs_credential_expiry:
                        log.debug(
                            f'checkout: Disconnecting pool engine since it is after {self._rs_credential_expiry}'
                        )
                        raise DisconnectionError(f"Credentials expired")
                    else:
                        log.debug(
                            f'checkout: Engine still valid. Good until {self._rs_credential_expiry}'
                        )

                    try:
                        with dbapi_connection.cursor() as cur:
                            cur.execute("SELECT 1")
                        log.debug(
                            'checkout: Query ping OK'
                        )
                    except Exception as err:
                        log.debug(
                            f"checkout: Query ping failed with {err}. Disconnect"
                        )
                        raise DisconnectionError(f"Ping error: {err}")
                # End engine receive_checkout

                @event.listens_for(self._engine, 'engine_connect')
                def receive_engine_connect(connection, **kwargs):
                    """
                    listen for the 'engine_connect' event
                    """
                    log.debug(
                        f'engine_connect: Creds expire {self._rs_credential_expiry}'
                    )
                    # https://docs.sqlalchemy.org/en/20/core/pooling.html#pool-disconnects-pessimistic
                    try:
                        # run a SELECT 1.   use a core select() so that
                        # the SELECT of a scalar value without a table is
                        # appropriately formatted for the backend
                        connection.scalar(select(1))
                        log.debug(
                            'engine_connect: Query ping OK'
                        )
                    except DBAPIError as err:
                        # catch SQLAlchemy's DBAPIError, which is a wrapper
                        # for the DBAPI's exception.  It includes a .connection_invalidated
                        # attribute which specifies if this connection is a "disconnect"
                        # condition, which is based on inspection of the original exception
                        # by the dialect in use.
                        log.warning(
                            f"engine_connect: Query ping failed with {err}"
                        )
                        if err.connection_invalidated:
                            # run the same SELECT again - the connection will re-validate
                            # itself and establish a new connection.  The disconnect detection
                            # here also causes the whole connection pool to be invalidated
                            # so that all stale connections are discarded.
                            connection.scalar(select(1))
                            log.debug(
                                f"engine_connect: Query second ping OK"
                            )
                        else:
                            log.error(
                                f"engine_connect: Connection was not invalidated with {err}"
                            )
                            raise
                # End receive_engine_connect

                # @event.listens_for(self._engine, 'engine_disposed')
                # def receive_engine_disposed(engine):
                #     """
                #     listen for the 'engine_disposed' event
                #     """
                #     log.debug(
                #         f'engine_disposed: Creds expire {self._rs_credential_expiry}'
                #     )

                @event.listens_for(self._engine, "handle_error")
                def handle_exception(context: ExceptionContext) -> None:
                    """
                    sqlalchemy-redshift Version: 1.0.0 does not catch IAM Authentication errors as disconnection errors
                    """
                    log.debug(f"handle_error: {context.original_exception}")
                    if (not context.is_disconnect
                            and 'IAM Authentication token has expired' in str(context.original_exception)
                    ):
                        # noinspection PyUnresolvedReferences,PyDunderSlots
                        context.invalidate_pool_on_disconnect = True
                        # noinspection PyUnresolvedReferences,PyDunderSlots
                        context.is_disconnect = True
                        log.error(
                            f"handle_error: Creds expire {self._rs_credential_expiry} "
                            f"but got error {context.original_exception}. "
                            f"This was early by {(self._rs_credential_expiry - self._now()).total_seconds()} seconds. "
                            "Forcing creds as expired (date in 1970)."
                        )
                        self._rs_credential_expiry = datetime(1970, 1, 1, tzinfo=timezone.utc)
                        try:
                            # noinspection PyUnresolvedReferences
                            if context.pool_pre_ping:
                                log.error(f"Error above was during pool_pre_ping")
                        except AttributeError:
                            pass

                    return None

        return self._engine

    def raw_connection(self):
        """
        Return a "raw" DBAPI connection from the connection pool.

        See https://docs.sqlalchemy.org/en/20/core/connections.html#sqlalchemy.engine.Engine.raw_connection
        """
        return self.get_engine().raw_connection()

    def connect(self) -> 'sqlalchemy.engine.base.Connection':
        """
        Connect to the configured database.
        Special handling for sqlite where subsequent calls will return the same connection.
        """
        if self.dialect == 'sqlite':
            # noinspection PyUnresolvedReferences
            if self._sqlite_connection is None or self._sqlite_connection.closed:
                self._sqlite_connection = self.get_engine().connect()
            return self._sqlite_connection
        else:
            return self.get_engine().connect()

    def session(self) -> Session:
        """
        Build a SQLAlchemy session from the configured database.
        """
        return Session(bind=self.get_engine())
