from copy import copy
from typing import *
from pathlib import PurePosixPath, Path

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
        self.resource.upload_file(
            Filename=local_filename,
            Bucket=self.bucket_name,
            Key=key,
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
            Filename=local_filename,
            ExtraArgs=extra_args,
            Config=transfer_config,
        )

    def delete_by_key(self, key: Union[str, PurePosixPath]):
        self.client.delete_object(Bucket=self.bucket_name, Key=str(key))

    def list_object_keys(self, key: Union[str, PurePosixPath]) -> List[str]:
        paginator = self.client.get_paginator('list_objects_v2')
        response = paginator.paginate(Bucket=self.bucket_name, Prefix=key)
        return [object['Key'] for object in response['Contents']]


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

    def get_copy(self, copied_by: str = 'get_copy') -> 'S3_Bucket_Folder':
        new_folder = self.copy(deep=True)
        new_folder._root_config = self._root_config
        new_folder._parents = self._parents + [copied_by]
        return new_folder

    def joinpath(self, *other) -> 'S3_Bucket_Folder':
        new_folder = self.get_copy(copied_by=f".join({other})")
        new_key = PurePosixPath(self.folder, *other)
        new_folder.folder = str(new_key)
        return new_folder

    def list_object_keys(self, key: Union[str, PurePosixPath]) -> List[str]:
        if key is None:
            key = self.folder
        return super().list_object_keys(key=key)


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
