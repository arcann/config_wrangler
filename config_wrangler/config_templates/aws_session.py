from typing import *
from pathlib import PurePosixPath, Path

from pydantic import PrivateAttr

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

    def get_resource(self, service: str = None):
        if service is None:
            service = self._service
        return self.session.resource(service, region_name=self.region_name)

    def get_client(self, service: str = None):
        if service is None:
            service = self._service
        return self.session.client(service, region_name=self.region_name)
