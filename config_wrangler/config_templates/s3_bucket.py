from pathlib import PurePosixPath, Path
from typing import *

from boto3.s3.transfer import TransferConfig
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


class S3_Bucket(AWS_Session):
    bucket_name: str
    region_name: str = None

    _service: str = PrivateAttr(default='s3')

    def get_bucket(self) -> 'botostubs.S3.S3Resource.Bucket':
        return self.resource.Bucket(self.bucket_name)

    def __str__(self):
        return f"s3://{self.bucket_name}"

    def upload_file(
        self,
        local_filename: Union[str, Path],
        key: Union[str, PurePosixPath],
        extra_args: Optional[dict] = None,
        transfer_config: Optional[TransferConfig] = None,
    ):
        self.client.upload_file(
            Filename=str(local_filename),
            Bucket=self.bucket_name,
            Key=str(key),
            ExtraArgs=extra_args,
            Config=transfer_config,
        )

    def download_file(
            self,
            key: Union[str, PurePosixPath],
            local_filename: Union[str, Path],
            extra_args: Optional[dict] = None,
            transfer_config: Optional[TransferConfig] = None,
    ):
        self.resource.Bucket(self.bucket_name).download_file(
            Key=str(key),
            Filename=str(local_filename),
            ExtraArgs=extra_args,
            Config=transfer_config,
        )

    def get_object(self, key: Union[str, PurePosixPath]):
        return self.resource.Object(self.bucket_name, str(key))

    def delete_by_key(self, key: Union[str, PurePosixPath]):
        self.client.delete_object(Bucket=self.bucket_name, Key=str(key))

    def find_objects(self, key: Union[str, PurePosixPath] = None) -> Iterable['botostubs.S3.S3Resource.ObjectSummary']:
        if key is None:
            key = ''
        collection = self.resource.Bucket(self.bucket_name).objects.filter(Prefix=str(key))
        return collection

    def list_object_keys(self, key: Union[str, PurePosixPath] = None) -> List[str]:
        obj_collecion = self.find_objects(key)
        return [obj.key for obj in obj_collecion]

    def list_object_paths(self, key: Union[str, PurePosixPath]) -> List[PurePosixPath]:
        return [PurePosixPath(key) for key in self.list_object_keys(key)]

    def get_copy(self, copied_by: str = 'get_copy') -> 'S3_Bucket':
        new_instance = self.copy(deep=False)
        try:
            self.set_as_child(copied_by, new_instance)
        except AttributeError:
            # Make the copy it's own root
            new_instance._root_config = new_instance
            new_instance._parents = []
        return new_instance

    def nav_to_bucket(self, bucket_name) -> 'S3_Bucket':
        new_instance = self.get_copy()
        new_instance.bucket_name = bucket_name
        return new_instance


class S3_Bucket_Folder(S3_Bucket):
    folder: str

    def __str__(self):
        return f"s3://{self.bucket_name}/{self.folder}"

    def upload_folder_file(
        self,
        local_filename: Union[str, Path],
        key_suffix: Union[str, PurePosixPath],
        extra_args: Optional[dict] = None,
        transfer_config: Optional[TransferConfig] = None,
    ):
        full_key = PurePosixPath(self.folder, key_suffix)
        super().upload_file(
            local_filename=local_filename,
            key=full_key,
            extra_args=extra_args,
            transfer_config=transfer_config,
        )

    def download_folder_file(
            self,
            key_suffix: Union[str, PurePosixPath],
            local_filename: Union[str, Path],
            extra_args: Optional[dict] = None,
            transfer_config: Optional[TransferConfig] = None,
    ):
        full_key = PurePosixPath(self.folder, key_suffix)
        super().download_file(
            key=full_key,
            local_filename=local_filename,
            extra_args=extra_args,
            transfer_config=transfer_config,
        )

    def joinpath(self, *other) -> 'S3_Bucket_Folder':
        new_folder = self.get_copy(copied_by=f".join({other})")
        new_key = PurePosixPath(self.folder, *other)
        new_folder.folder = str(new_key)
        return new_folder

    def __truediv__(self, other) -> 'S3_Bucket_Folder':
        return self.joinpath(other)

    def key_exists(self, key: Union[str, PurePosixPath]):
        try:
            self.client.head_object(Bucket=self.bucket_name, Key=str(key))
            return True
        except Exception:
            return False

    def list_object_keys(self, key: Union[str, PurePosixPath] = None) -> List[str]:
        if key is None:
            key = self.folder
        return super().list_object_keys(key=key)

    def list_object_paths(self, key: Union[str, PurePosixPath] = None) -> List[PurePosixPath]:
        if key is None:
            key = self.folder
        return super().list_object_paths(key=key)


class S3_Bucket_Folder_File(S3_Bucket_Folder):
    folder: str
    file_name: str

    def __str__(self):
        return f"s3://{self.bucket_name}/{self.folder}/{self.file_name}"

    def upload_specified_file(
        self,
        local_filename: Union[str, PurePosixPath],
        extra_args: Optional[dict] = None,
        transfer_config: Optional[TransferConfig] = None,
    ):
        super().upload_folder_file(
            local_filename=local_filename,
            key_suffix=self.file_name,
            extra_args=extra_args,
            transfer_config=transfer_config,
        )

    def download_specified_file(
        self,
        local_filename: Union[str, PurePosixPath],
        extra_args: Optional[dict] = None,
        transfer_config: Optional[TransferConfig] = None,
    ):
        super().download_folder_file(
            local_filename=local_filename,
            key_suffix=self.file_name,
            extra_args=extra_args,
            transfer_config=transfer_config,
        )


class S3_Bucket_Key(S3_Bucket):
    key: str

    def __str__(self):
        return f"s3://{self.bucket_name}/{self.key}"

    def upload_specified_file(
        self,
        local_filename: Union[str, PurePosixPath],
        extra_args: Optional[dict] = None,
        transfer_config: Optional[TransferConfig] = None,
    ):
        super().upload_file(
            local_filename=local_filename,
            key=self.key,
            extra_args=extra_args,
            transfer_config=transfer_config,
        )

    def download_specified_file(
        self,
        local_filename: Union[str, PurePosixPath],
        extra_args: Optional[dict] = None,
        transfer_config: Optional[TransferConfig] = None,
    ):
        super().download_file(
            local_filename=local_filename,
            key=self.key,
            extra_args=extra_args,
            transfer_config=transfer_config,
        )
