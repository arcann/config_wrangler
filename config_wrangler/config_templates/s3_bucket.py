from typing import *
from pathlib import PurePosixPath, Path

from pydantic import PrivateAttr

from config_wrangler.config_templates.aws_session import AWS_Session

try:
    import boto3
except ImportError:
    raise ImportError("S3_Bucket requires boto3 to be installed")

if TYPE_CHECKING:
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


class S3_Bucket(AWS_Session):
    bucket_name: str
    region_name: str = None

    _service: str = PrivateAttr(default='s3')

    def get_connection(self) -> 'botostubs.S3.S3Resource':
        return self.get_client()

    def get_bucket(self, connection=None) -> 'botostubs.S3.S3Resource.Bucket':
        if connection is None:
            connection = self.get_connection()
        return connection.Bucket(self.bucket_name)

    def __str__(self):
        return f"s3://{self.bucket_name}"

    def upload_file(
        self,
        filename: Union[str, Path],
        key: Union[str, PurePosixPath],
    ):
        self.get_connection().upload_file(
            Filename=filename,
            Bucket=self.bucket_name,
            Key=key,
        )


class S3_Bucket_Folder(S3_Bucket):
    folder: str

    def __str__(self):
        return f"s3://{self.bucket_name}/{self.folder}"

    def upload_file(
        self,
        filename: Union[str, Path],
        key_suffix: Union[str, PurePosixPath],
    ):
        full_key = PurePosixPath(self.folder, key_suffix)
        super().upload_file(
            filename=filename,
            key=full_key,
        )
