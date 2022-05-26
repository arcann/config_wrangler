from typing import *

from pydantic import PrivateAttr


try:
    import boto3
except ImportError:
    raise ImportError("S3_Bucket requires boto3 to be installed")

if TYPE_CHECKING:
    from config_wrangler.config_templates.s3_bucket import S3_Bucket, S3_Bucket_Key, S3_Bucket_Folder
    try:
        import botostubs
    except ImportError:
        botostubs = None

# NOTE: If you are not seeing botostubs code completion in Intellij-based IDEs,
#       please increase the intellisense filesize limit
#       e.g `idea.max.intellisense.filesize=20000` in IDE custom properties
#       (Help > Edit Custom Properties), then restart.
#       https://github.com/jeshan/botostubs#notes

from config_wrangler.config_templates.credentials import Credentials


class AWS_Session(Credentials):
    region_name: str = None

    _session = PrivateAttr(default=None)
    _service: str = PrivateAttr(default=None)

    @property
    def session(self):
        if self._session is None:
            self._session = boto3.session.Session(
                aws_access_key_id=self.user_id,
                aws_secret_access_key=self.get_password(),
                region_name=self.region_name,
            )
        return self._session

    @property
    def resource(self):
        return self._get_resource()

    @property
    def client(self):
        return self._get_client()

    def _get_resource(self, service: str = None):
        if service is None:
            service = self._service
        return self.session.resource(service, region_name=self.region_name)

    def _get_client(self, service: str = None):
        if service is None:
            service = self._service
        return self.session.client(service, region_name=self.region_name)

    def get_copy(self, copied_by: str = 'get_copy') -> 'AWS_Session':
        return cast('AWS_Session', super().get_copy(copied_by))

    def nav_to_bucket(self, bucket_name) -> 'S3_Bucket':
        from config_wrangler.config_templates.s3_bucket import S3_Bucket

        return S3_Bucket(
            bucket_name=bucket_name,
            **self._dict_for_init()
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

    def nav_to_s3_link(self, s3_uri: str) -> Union['S3_Bucket_Key', 'S3_Bucket_Folder']:
        bucket, key = self.split_s3_uri(s3_uri)
        return self.nav_to_bucket(bucket) / key
