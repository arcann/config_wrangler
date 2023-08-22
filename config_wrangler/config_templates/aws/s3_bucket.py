from functools import lru_cache
from pathlib import PurePosixPath, Path
from typing import *

from boto3.s3.transfer import TransferConfig
from pydantic import field_validator, PrivateAttr

from config_wrangler.config_templates.aws.aws_session import AWS_Session

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

    @staticmethod
    @lru_cache(maxsize=128)
    def _get_bucket_region(client, bucket_name) -> str:
        location = client.get_bucket_location(Bucket=bucket_name)
        if location is None or location['LocationConstraint'] is None:
            # https://docs.aws.amazon.com/AmazonS3/latest/API/API_CreateBucket.html#API_CreateBucket_RequestSyntax
            # If you don't specify a Region, the bucket is created in the US East (N. Virginia) Region (us-east-1).
            return 'us-east-1'
        else:
            return location['LocationConstraint']

    def get_bucket_region(self) -> str:
        """
        Get the region_name from the actual S3 bucket definition.

        NOTE:
            This can differ from the region_name attribute specified in the init call to this class
            or the config file that loads it.
            The region_name attribute is used for establishing the AWS session.
            get_bucket_region() is used to find out in which region the data is stored.
        """
        return S3_Bucket._get_bucket_region(self.client, self.bucket_name)

    def upload_file(
            self,
            local_filename: Union[str, Path],
            key: Union[str, PurePosixPath],
            extra_args: Optional[dict] = None,
            transfer_config: Optional[TransferConfig] = None,
    ):
        if transfer_config is None:
            transfer_config = TransferConfig(multipart_threshold=5* (1024**3))  # 5 GB

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
            create_parents: bool = True,
    ):
        if create_parents:
            local_path = Path(local_filename)
            local_path.parent.mkdir(parents=True, exist_ok=True)
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
        return self._build_s3_bucket_key(key)

    def nav_to_folder(
            self,
            folder: Union[str, Path]
    ) -> 'S3_Bucket_Folder':
        return self._build_s3_bucket_folder(folder)

    def nav_to_relative_folder(
            self,
            folder: Union[str, Path]
    ) -> 'S3_Bucket_Folder':
        return self._build_s3_bucket_folder(folder)

    def __truediv__(
            self, other: Union[str, Path]
    ) -> 'S3_Bucket_Key':
        return self.nav_to_key(other)

    # noinspection SpellCheckingInspection
    def joinpath(
        self,
        *others
    ) -> Union[
        'S3_Bucket_Key',
        'S3_Bucket_Folder'
    ]:
        new_path = self
        for other in others:
            new_path = new_path / other
        return new_path

    def _build_s3_bucket_folder(self, folder: Union[str, Path]):
        return self._factory(
            S3_Bucket_Folder,
            exclude={'file_name'},
            folder=str(folder)
        )

    def _build_s3_bucket_folder_file(self, file_name: Union[str, Path], folder: Union[str, Path] = None):
        if folder is None:
            return self._factory(
                S3_Bucket_Folder_File,
                exclude={'key'},
                file_name=str(file_name)
            )
        else:
            return self._factory(
                S3_Bucket_Folder_File,
                exclude={'key'},
                folder=str(folder),
                file_name=str(file_name)
            )

    def _build_s3_bucket_key(self, key: Union[str, Path]):
        return self._factory(S3_Bucket_Key, key=str(key), exclude={'folder', 'file_name'})


class S3_Bucket_Folder(S3_Bucket):
    """
        Represents a folder within an S3 bucket.
    """
    folder: str

    # noinspection PyMethodParameters
    @field_validator('folder')
    @classmethod
    def validate_folder(cls, v):
        # Handle pathlib values
        if not isinstance(v, str):
            v = str(v)
        if len(v) == 0:
            raise ValueError(f"Zero length string not a valid folder")
        return v

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
            create_parents: bool = True,
    ):
        full_key = PurePosixPath(self.folder, key_suffix)
        super().download_file(
            key=full_key,
            local_filename=local_filename,
            extra_args=extra_args,
            transfer_config=transfer_config,
            create_parents=create_parents,
        )

    def nav_to_folder(self, folder_key: Union[str, Path]) -> 'S3_Bucket_Folder':
        return self._build_s3_bucket_folder(folder_key)

    def nav_to_relative_folder(self, folder: Union[str, Path]) -> 'S3_Bucket_Folder':
        new_path = PurePosixPath(self.folder) / folder
        return self.nav_to_folder(new_path)

    def nav_to_file(
            self,
            file_name: Union[str, Path]
    ) -> 'S3_Bucket_Folder_File':
        return self._build_s3_bucket_folder_file(
            file_name
        )

    def __truediv__(
            self, other: Union[str, Path]
    ) -> 'S3_Bucket_Key':
        new_path = PurePosixPath(self.folder) / other
        return self.nav_to_key(new_path)

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
    file_name: str

    # noinspection PyMethodParameters
    @field_validator('file_name')
    @classmethod
    def validate_file_name(cls, v):
        # Handle pathlib values
        if not isinstance(v, str):
            v = str(v)
        if len(v) == 0:
            raise ValueError(f"Zero length string not a valid file_name")
        return v

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

    def __truediv__(
            self, other: Union[str, Path]
    ) -> 'S3_Bucket_Key':
        # Probably an error but we can try assuming that file_name is actually a folder name
        new_path = PurePosixPath(self.folder) / self.file_name / other
        return self.nav_to_key(new_path)


class S3_Bucket_Key(S3_Bucket):
    """
    Represents a unique file (key) within an S3 bucket.
    Similar to S3_Bucket_Folder_File but uses a single key instead of folder + file_name
    """
    key: str

    # noinspection PyMethodParameters
    @field_validator('key')
    @classmethod
    def validate_key(cls, v):
        # Handle pathlib values
        if not isinstance(v, str):
            v = str(v)
        if len(v) == 0:
            raise ValueError(f"Zero length string not a valid key")
        return v

    def __str__(self):
        return f"s3://{self.bucket_name}/{self.key}"

    def get_copy(self, copied_by: str = 'get_copy') -> 'S3_Bucket_Key':
        return cast('S3_Bucket_Key', super().get_copy(copied_by))

    def nav_to_key(self, key) -> 'S3_Bucket_Key':
        return self._build_s3_bucket_key(key)

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
        create_parents: bool = True,
    ):
        super().download_file(
            local_filename=local_filename,
            key=self.key,
            extra_args=extra_args,
            transfer_config=transfer_config,
            create_parents=create_parents,
        )

    def get_object(self, key: Union[str, PurePosixPath] = None, version_id=None):
        if key is None:
            key = self.key
        return super().get_object(key=key)

    def list_object_keys(self, key: Union[str, PurePosixPath] = None) -> List[str]:
        if key is None:
            key = self.key
        return super().list_object_keys(key=key)

    def list_object_paths(self, key: Union[str, PurePosixPath] = None) -> List[PurePosixPath]:
        if key is None:
            key = self.key
        return super().list_object_paths(key=key)

    def find_objects(self, key: Union[str, PurePosixPath] = None) -> Iterable['botostubs.S3.S3Resource.ObjectSummary']:
        if key is None:
            key = self.key
        return super().find_objects(key)

    def nav_to_folder(
            self,
            folder: Union[str, Path]
    ) -> 'S3_Bucket_Folder':
        return self._build_s3_bucket_folder(folder)

    def nav_to_relative_folder(
            self,
            folder: Union[str, Path]
    ) -> 'S3_Bucket_Folder':
        new_path = PurePosixPath(self.key) / folder
        return self.nav_to_folder(new_path)

    def nav_to_file(
            self,
            file_name: Union[str, Path]
    ) -> 'S3_Bucket_Folder_File':
        return self._build_s3_bucket_folder_file(
            folder=self.key,
            file_name=file_name
        )

    def __truediv__(
            self, other: Union[str, Path]
    ) -> 'S3_Bucket_Key':
        new_path = PurePosixPath(self.key) / other
        return self.nav_to_key(new_path)
