import typing
try:
    import boto3
except ImportError:
    raise ImportError("S3_Bucket requires boto3 to be installed")

if typing.TYPE_CHECKING:
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


class S3_Bucket(Credentials):
    bucket_name: str

    def get_connection(self) -> 'botostubs.S3.S3Resource':
        return boto3.resource(
            's3',
            aws_access_key_id=self.user_id,
            aws_secret_access_key=self.get_password()
        )

    def get_bucket(self, connection=None) -> 'botostubs.S3.S3Resource.Bucket':
        if connection is None:
            connection = self.get_connection()
        return connection.Bucket(self.bucket_name)

