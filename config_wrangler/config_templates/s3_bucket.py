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

    def key_exists(self, key: Union[str, PurePosixPath]) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket_name, Key=str(key))
            return True
        except Exception:
            return False

    def get_object(self, key: Union[str, PurePosixPath]):
        return self.resource.Object(self.bucket_name, str(key))

    def delete_by_key(self, key: Union[str, PurePosixPath], version_id: str = None):
        kwargs = {
            'Bucket': self.bucket_name,
            'Key': str(key),
        }
        if version_id is not None:
            kwargs['VersionId'] = version_id
        self.client.delete_object(**kwargs)

    def find_objects(self, key: Union[str, PurePosixPath] = None) -> Iterable['botostubs.S3.S3Resource.ObjectSummary']:
        if key is None:
            key = ''
        collection = self.resource.Bucket(self.bucket_name).objects.filter(Prefix=str(key))
        return collection

    def list_object_keys(self, key: Union[str, PurePosixPath] = None) -> List[str]:
        obj_collection = self.find_objects(key)
        return [obj.key for obj in obj_collection]

    def list_object_paths(self, key: Union[str, PurePosixPath]) -> List[PurePosixPath]:
        return [PurePosixPath(key) for key in self.list_object_keys(key)]

    def get_copy(self, copied_by: str = 'get_copy') -> 'S3_Bucket':
        return cast('S3_Bucket', super().get_copy(copied_by))

    def nav_to_key(self, key) -> 'S3_Bucket_Key':
        return S3_Bucket_Key(
            key=key,
            **self._dict_for_init(exclude={'key'})
        )

    def nav_to_folder(self, folder) -> 'S3_Bucket_Folder':
        return S3_Bucket_Folder(
            folder=folder,
            **self._private_attr_dict(),
            **self._dict_for_init(exclude={'folder'})
        )

    def __truediv__(self, key) -> Union['S3_Bucket_Key', 'S3_Bucket_Folder']:
        if key[-1] == '/' or key == '':
            return self.nav_to_folder(key)
        else:
            return self.nav_to_key(key)


class S3_Bucket_Folder(S3_Bucket):
    """
        Represents a folder within an S3 bucket.
    """
    folder: str

    def __str__(self):
        return f"s3://{self.bucket_name}/{self.folder}"

    def get_copy(self, copied_by: str = 'get_copy') -> 'S3_Bucket_Folder':
        return cast('S3_Bucket_Folder', super().get_copy(copied_by))

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

    def nav_to_folder(self, folder_key) -> 'S3_Bucket_Folder':
        new_folder = self.get_copy(copied_by=f".nav_to_folder({folder_key})")
        new_folder.folder = folder_key
        return new_folder

    def nav_to_file(self, file_name) -> 'S3_Bucket_Folder_File':
        new_folder_file = S3_Bucket_Folder_File(
            file_name=file_name,
            **self._dict_for_init(exclude={'file_name'})
        )
        new_folder_file.file_name = file_name
        return new_folder_file

    def joinpath(self, *other) -> 'S3_Bucket_Folder':
        new_folder = self.get_copy(copied_by=f".joinpath({other})")
        new_key = PurePosixPath(self.folder, *other)
        new_folder.folder = str(new_key)
        return new_folder

    def __truediv__(self, other) -> 'S3_Bucket_Folder':
        return self.joinpath(other)

    def list_object_keys(self, key: Union[str, PurePosixPath] = None) -> List[str]:
        if key is None:
            key = self.folder
        return super().list_object_keys(key=key)

    def list_object_paths(self, key: Union[str, PurePosixPath] = None) -> List[PurePosixPath]:
        if key is None:
            key = self.folder
        return super().list_object_paths(key=key)

    def key_exists(self, key: Union[str, PurePosixPath] = None) -> bool:
        if key is None:
            key = self.folder
        return super().key_exists(key)


class S3_Bucket_Folder_File(S3_Bucket_Folder):
    """
        Represents a unique folder & file within an S3 bucket.
        Similar to S3_Bucket_Key but uses folder + file_name instead of a single key.
    """
    folder: str
    file_name: str

    def __str__(self):
        return f"s3://{self.bucket_name}/{self.folder}/{self.file_name}"

    def get_copy(self, copied_by: str = 'get_copy') -> 'S3_Bucket_Folder_File':
        return cast('S3_Bucket_Folder_File', super().get_copy(copied_by))

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

    def get_object(self, key: Union[str, PurePosixPath] = None):
        if key is None:
            key = f"{self.folder}/{self.file_name}"
        return super().get_object(key=key)


class S3_Bucket_Key(S3_Bucket):
    """
    Represents a unique file (key) within an S3 bucket.
    Similar to S3_Bucket_Folder_File but uses a single key instead of folder + file_name
    """
    key: str

    def __str__(self):
        return f"s3://{self.bucket_name}/{self.key}"

    def get_copy(self, copied_by: str = 'get_copy') -> 'S3_Bucket_Key':
        return cast('S3_Bucket_Key', super().get_copy(copied_by))

    def nav_to_key(self, key) -> 'S3_Bucket_Key':
        new_bucket_key = self.get_copy(copied_by=f".nav_to_key({key})")
        new_bucket_key.file_name = key
        return new_bucket_key

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

    def get_object(self, key: Union[str, PurePosixPath] = None, version_id=None):
        if key is None:
            key = self.key
        return super().get_object(key=key)
