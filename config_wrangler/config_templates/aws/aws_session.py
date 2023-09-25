from typing import *

from pydantic import PrivateAttr

try:
    import boto3
except ImportError:
    raise ImportError("AWS_Session requires boto3 to be installed")

if TYPE_CHECKING:
    from config_wrangler.config_templates.aws.s3_bucket import S3_Bucket, S3_Bucket_Key

# NOTE: If you are not seeing boto3-stubs code completion in Intellij-based IDEs,
#       please increase the intellisense filesize limit
#       e.g `idea.max.intellisense.filesize=20000` in IDE custom properties
#       (Help > Edit Custom Properties), then restart.

from config_wrangler.config_templates.credentials import Credentials


# AWSSession does not look right, so we added underscores
# noinspection PyPep8Naming
class AWS_Session(Credentials):
    # sso_session: Optional[DynamicallyReferenced] = None
    region_name: Optional[str] = None

    _session: boto3.session.Session = PrivateAttr(default=None)
    _service: str = PrivateAttr(default=None)

    @property
    def session(self) -> boto3.session.Session:
        if self._session is None:
            self._session = boto3.session.Session(
                aws_access_key_id=self.user_id,
                aws_secret_access_key=self.get_password(),
                region_name=self.region_name,
            )
        return self._session

    def set_session(self, session: boto3.session.Session):
        self._session = session

    @property
    def has_session(self) -> bool:
        return self._session is not None

    @property
    def resource(self):
        return self._get_resource()

    @property
    def client(self):
        return self._get_client()

    def _get_resource(self, service: str = None):
        if service is None:
            service = self._service
        # noinspection PyTypeChecker
        return self.session.resource(service, region_name=self.region_name)

    def _get_client(self, service: str = None):
        if service is None:
            service = self._service
        # noinspection PyTypeChecker
        return self.session.client(service, region_name=self.region_name)

    def get_copy(self, copied_by: str = 'get_copy') -> 'AWS_Session':
        return self._factory(cls=self.__class__)

    def _factory(self, cls, exclude: Set[str] = None, **attributes):
        if exclude is None:
            exclude = set()
        exclude.update(attributes.keys())
        new_object = cls.model_construct(
            **attributes,
            **self._dict_for_init(exclude=exclude)
        )
        self.add_child(str(cls), new_object)
        if self.has_session:
            new_object.set_session(self.session)
        return new_object

    def nav_to_bucket(self, bucket_name) -> 'S3_Bucket':
        from config_wrangler.config_templates.aws.s3_bucket import S3_Bucket
        return self._factory(
            S3_Bucket,
            exclude={'bucket_name', 'folder', 'file_name', 'key'},
            bucket_name=bucket_name,
        )

    @staticmethod
    def split_s3_uri(s3_uri: str) -> Tuple[str, str]:
        parts = s3_uri.split("/", 3)
        # Note 'S3://bucket-name/key-name/file.txt'.split('/', 3)
        # Returns ['S3:', '', 'bucket-name', 'key-name/file.txt']
        if parts[0].lower() != 's3:' or parts[1] != '':
            raise ValueError(f"S3 URI '{s3_uri}' does not appear to be valid")
        if len(parts) == 3:
            return parts[2], ''
        else:
            return parts[2], parts[3]

    def nav_to_s3_link(self, s3_uri: str) -> 'S3_Bucket_Key':
        bucket, key = self.split_s3_uri(s3_uri)
        return self.nav_to_bucket(bucket) / key
