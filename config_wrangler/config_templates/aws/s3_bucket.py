import io
import logging
import warnings
from datetime import datetime, timezone
from enum import auto, Enum
from functools import lru_cache
from pathlib import PurePosixPath, Path, PurePath
from typing import *

from cachetools import cached, TTLCache
from pydantic import field_validator, PrivateAttr

from config_wrangler.config_exception import ConfigError
from config_wrangler.config_templates.aws.aws_session import AWS_Session

# noinspection PyProtectedMember

try:
    import boto3
    from boto3.s3.transfer import TransferConfig
    from botocore.exceptions import ClientError
    from botocore.response import StreamingBody

    # Unfortunately, the NoSuchKey exception below does not reliably work. ClientError is used instead
    # s3_unconnected_client = boto3.client('s3')
    # NoSuchKey = s3_unconnected_client.exceptions.NoSuchKey

    ERROR_S3_NOT_FOUND = {'404', 'NoSuchKey'}

    # Also note the following list of error codes:
    # https://docs.aws.amazon.com/AmazonS3/latest/API/ErrorResponses.html#ErrorCodeList
except ImportError:
    raise ImportError("S3_Bucket requires boto3 to be installed")

if TYPE_CHECKING:
    # https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/client/
    from mypy_boto3_s3.client import S3Client

    # https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/service_resource/
    from mypy_boto3_s3.service_resource import Bucket
    from mypy_boto3_s3.service_resource import Object
    from mypy_boto3_s3.service_resource import ObjectSummary
    from mypy_boto3_s3.service_resource import BucketObjectsCollection
    from mypy_boto3_s3.service_resource import S3ServiceResource

# NOTE: If you are not seeing boto3-stubs code completion in Intellij-based IDEs,
#       please increase the intellisense filesize limit
#       e.g `idea.max.intellisense.filesize=20000` in IDE custom properties
#       (Help > Edit Custom Properties), then restart.

local_timezone = datetime.now(timezone.utc).astimezone().tzinfo


class S3ClientError(ClientError):
    def __init__(self, message: str, original_error: Optional[ClientError]):
        Exception.__init__(self, message)
        if original_error is not None:
            self.response = original_error.response
            self.operation_name = original_error.operation_name
        else:
            self.response = {
                'Error': {
                    'Code': 'Unknown',
                    'Message': message,
                }
            }
            self.operation_name = 'Unknown'


# noinspection PyPep8Naming
class S3_Bucket(AWS_Session):
    bucket_name: str
    key: Optional[str] = None

    _service: str = PrivateAttr(default='s3')

    class OverwriteModes(Enum):
        ALWAYS_OVERWRITE = auto()
        OVERWRITE_OLDER = auto()
        NEVER_OVERWRITE = auto()

    def __str__(self):
        key = self._get_key()
        if key == '':
            return f"s3://{self.bucket_name}"
        else:
            return f"s3://{self.bucket_name}/{key}"

    def __hash__(self):
        return hash(str(self))

    @property
    def resource(self) -> 'S3ServiceResource':
        return super().resource

    @property
    def client(self) -> 'S3Client':
        return super().client

    @staticmethod
    def _boto3_error(ex: ClientError) -> str:
        return ex.response.get('Error', {}).get('Code')

    @staticmethod
    def _boto3_error_match(ex: ClientError, error_set: Set[str]) -> bool:
        return S3_Bucket._boto3_error(ex) in error_set

    def get_boto3_bucket(self) -> 'Bucket':
        # Might raise error code NoSuchBucket
        return self.resource.Bucket(self.bucket_name)

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

    @staticmethod
    def _non_blank_key(key: str):
        if key is None or str(key).strip() == '':
            return False
        else:
            return True

    @staticmethod
    def _is_blank_key(key: str):
        return not S3_Bucket._non_blank_key(key)

    def _get_key(self, extra_key: Optional[Union[str, PurePosixPath]] = None) -> str:
        if self._is_blank_key(extra_key):
            if self._is_blank_key(self.key):
                key = ''
            else:
                key = self.key
        else:
            if self._is_blank_key(self.key):
                key = extra_key
            else:
                key = str(PurePosixPath(self.key) / extra_key)

        return key

    class CompareResult(Enum):
        DIFFERENT_SIZE = auto()
        LOCAL_NEWER = auto()
        SAME_TIMES = auto()
        LOCAL_OLDER = auto()

    @staticmethod
    def _compare_object_to_file(
            bucket_object: Union['Object', 'ObjectSummary'],
            local_filename: Path,
    ) -> CompareResult:
        s3_last_modified = bucket_object.last_modified
        s3_file_size = bucket_object.content_length

        local_stats = local_filename.stat()
        local_last_modified = datetime.fromtimestamp(
            local_stats.st_mtime,
            tz=local_timezone
        )
        local_file_size = local_stats.st_size

        if s3_file_size != local_file_size:
            return S3_Bucket.CompareResult.DIFFERENT_SIZE
        else:
            if local_last_modified > s3_last_modified:
                return S3_Bucket.CompareResult.LOCAL_NEWER
            elif local_last_modified == s3_last_modified:
                return S3_Bucket.CompareResult.SAME_TIMES
            else:
                return S3_Bucket.CompareResult.LOCAL_OLDER

    def upload_file(
            self,
            *,
            local_filename: Union[str, Path],
            key: Optional[Union[str, PurePosixPath]] = None,
            extra_args: Optional[dict] = None,
            transfer_config: Optional[TransferConfig] = None,
            overwrite_mode: OverwriteModes = OverwriteModes.ALWAYS_OVERWRITE
    ):
        if transfer_config is None:
            transfer_config = TransferConfig(multipart_threshold=5 * (1024**3))  # 5 GB

        if overwrite_mode == S3_Bucket.OverwriteModes.ALWAYS_OVERWRITE:
            do_upload = True
        else:
            try:
                bucket_object = self.get_object(key)
                if overwrite_mode == S3_Bucket.OverwriteModes.NEVER_OVERWRITE:
                    do_upload = False
                else:
                    local_filename = Path(local_filename)
                    compare_result = S3_Bucket._compare_object_to_file(bucket_object, local_filename)
                    if compare_result in {
                        S3_Bucket.CompareResult.DIFFERENT_SIZE,
                        S3_Bucket.CompareResult.LOCAL_NEWER
                    }:
                        do_upload = True
                    else:
                        do_upload = False
            except ClientError as ex:
                if self._boto3_error_match(ex, ERROR_S3_NOT_FOUND):
                    do_upload = True
                else:
                    raise

        if do_upload:
            key = self._get_key(key)
            self.client.upload_file(
                Filename=str(local_filename),
                Bucket=self.bucket_name,
                Key=key,
                ExtraArgs=extra_args,
                Config=transfer_config,
            )

    def open(
            self,
            mode: str = 'r',
            encoding: Optional[str] = None,
            errors: Optional[str] = None,
    ) -> io.IOBase:
        if mode is None or len(mode) == 0:
            raise ValueError('open mode required')
        if mode[0] != 'r':
            raise ValueError('S3 open mode only supports read (r, rt, rb)')

        as_text = True
        if len(mode) > 1:
            if mode[1] == 'b':
                as_text = False

        body: StreamingBody = self.get_object().get()['Body']
        # noinspection PyProtectedMember,PyTypeChecker
        bytes_stream = io.BufferedReader(body._raw_stream, 8192)

        if as_text:
            return io.TextIOWrapper(
                bytes_stream,
                encoding=encoding,
                errors=errors,
            )
        else:
            return bytes_stream

    def read_bytes(self) -> bytes:
        with self.open('rb') as f:
            return f.read()

    def read_text(self, encoding='utf-8', errors=None) -> str:
        with self.open('rb', encoding=encoding, errors=errors) as f:
            return f.read()

    def copy_to(
            self,
            target: Union[str, 'S3_Bucket_Key']
    ):
        if isinstance(target, str):
            target = self._build_s3_bucket_key(target)
        self_key = self._get_key()
        self.client.copy_object(
            Bucket=target.bucket_name,
            Key=target.key,
            CopySource=dict(
                Bucket=self.bucket_name,
                Key=self_key,
            )
        )

    def rename(self, target: str):
        self.copy_to(target)
        self.delete()

    def download_file(
            self,
            *,
            local_filename: Union[str, Path],
            key: Optional[Union[str, PurePosixPath]] = None,
            extra_args: Optional[dict] = None,
            transfer_config: Optional[TransferConfig] = None,
            create_parents: bool = True,
            overwrite_mode: OverwriteModes = OverwriteModes.OVERWRITE_OLDER,
            _bucket_object_summary: 'ObjectSummary' = None,
    ):
        if self._non_blank_key(key):
            file_obj = self / key
            file_obj.download_file(
                local_filename=local_filename,
                extra_args=extra_args,
                transfer_config=transfer_config,
                create_parents=create_parents,
                overwrite_mode=overwrite_mode,
                _bucket_object_summary=_bucket_object_summary,
            )
        else:
            log = logging.getLogger(f"{__name__}.download_file")
            local_path = Path(local_filename)
            if create_parents:
                local_path.parent.mkdir(parents=True, exist_ok=True)

            try:
                if overwrite_mode in {S3_Bucket.OverwriteModes.OVERWRITE_OLDER, S3_Bucket.OverwriteModes.NEVER_OVERWRITE}:
                    if local_path.exists():
                        if overwrite_mode == S3_Bucket.OverwriteModes.NEVER_OVERWRITE:
                            do_download = False
                            log.info(f"{self} download to {local_path} skipped since file exists and mode = {overwrite_mode}")
                        else:  # Check ages and size
                            if _bucket_object_summary is None:
                                bucket_object = self.get_object()
                            else:
                                bucket_object = _bucket_object_summary

                            compare_result = S3_Bucket._compare_object_to_file(bucket_object, local_path)

                            if compare_result in {
                                S3_Bucket.CompareResult.DIFFERENT_SIZE,
                                S3_Bucket.CompareResult.LOCAL_OLDER
                            }:
                                do_download = True
                                log.info(
                                    f"{self} download to {local_path} downloaded since file exists but {compare_result} "
                                    f"and mode = {overwrite_mode}"
                                )
                            else:
                                do_download = False
                                log.info(
                                    f"{self} download to {local_path} skipped since file exists {compare_result} "
                                    f"and mode = {overwrite_mode}"
                                )
                    else:
                        do_download = True
                        log.info(
                            f"{self} download to {local_path} downloaded since local file not not exist"
                        )
                else:
                    do_download = True
                    log.info(
                        f"{self} download to {local_path} downloaded since mode = {overwrite_mode}"
                    )
            except ClientError as ex:
                if self._boto3_error_match(ex, ERROR_S3_NOT_FOUND):
                    raise S3ClientError(f"{self} does not exist", ex)
                else:
                    raise S3ClientError(f"{self} with ID {self.user_id} get info yielded error {ex}", ex)
            except Exception as ex2:
                raise S3ClientError(f"{self} get info yielded error {ex2} {repr(ex2)}", None)

            if do_download:
                key = self._get_key()
                try:
                    self.resource.Bucket(self.bucket_name).download_file(
                        Key=key,
                        Filename=str(local_path),
                        ExtraArgs=extra_args,
                        Config=transfer_config,
                    )
                except ClientError as ex:
                    if self._boto3_error_match(ex, ERROR_S3_NOT_FOUND):
                        raise S3ClientError(f"{self} does not exist", ex)
                    else:
                        raise S3ClientError(f"{self} with ID {self.user_id} download yielded error {ex}", ex)

    def download_files(
            self,
            *,
            local_path: Union[str, Path],
            key: Optional[Union[str, PurePosixPath]] = None,
            extra_args: Optional[dict] = None,
            transfer_config: Optional[TransferConfig] = None,
            create_parents: bool = True,
            overwrite_mode: OverwriteModes = OverwriteModes.OVERWRITE_OLDER,
    ) -> Iterable[Path]:
        if self._non_blank_key(key):
            file_obj = self / key
            file_obj.download_files(
                local_path=local_path,
                extra_args=extra_args,
                transfer_config=transfer_config,
                create_parents=create_parents,
                overwrite_mode=overwrite_mode,
            )
        else:
            local_path = Path(local_path)
            if create_parents:
                local_path.parent.mkdir(parents=True, exist_ok=True)

            results = list()
            full_key = self._get_key()
            base_path = PurePosixPath(full_key)
            for s3_object in self.list_objects():
                s3_object_path = PurePosixPath(s3_object.key)
                try:
                    relative_key = s3_object_path.relative_to(base_path)
                except ValueError:
                    relative_key = s3_object_path.relative_to(base_path.parent)
                local_filename = local_path / relative_key
                s3_file = self._build_s3_bucket_key(s3_object.key)
                results.append(local_filename)
                s3_file.download_file(
                    local_filename=str(local_filename),
                    create_parents=create_parents,
                    extra_args=extra_args,
                    transfer_config=transfer_config,
                    overwrite_mode=overwrite_mode,
                    _bucket_object_summary=s3_object,
                )
            return results

    def exists(self, key: Optional[Union[str, PurePosixPath]] = None) -> bool:
        key = self._get_key(key)

        try:
            self.client.head_object(Bucket=self.bucket_name, Key=str(key))
            return True
        except ClientError as ex:
            if self._boto3_error_match(ex, ERROR_S3_NOT_FOUND):
                return False
            else:
                raise

    def key_exists(self, key: Union[str, PurePosixPath]) -> bool:
        warnings.warn(
            'The `key_exists` method is deprecated; use `exists` instead.',
            DeprecationWarning,
            stacklevel=2,
        )
        return self.exists(key)

    def get_object_uncached(self, key: Optional[Union[str, PurePosixPath]] = None) -> 'Object':
        key = self._get_key(key)
        return self.resource.Object(self.bucket_name, str(key))

    @cached(cache=TTLCache(maxsize=1024, ttl=10))
    def get_object(self, key: Optional[Union[str, PurePosixPath]] = None) -> 'Object':
        return self.get_object_uncached(key)

    def delete(
            self,
            key: Optional[Union[str, PurePosixPath]] = None,
            version_id: str = None,
    ):
        key = self._get_key(key)
        kwargs = {
            'Bucket': self.bucket_name,
            'Key': key,
        }
        if version_id is not None:
            kwargs['VersionId'] = version_id
        self.client.delete_object(**kwargs)

    def unlink(self, missing_ok=False):
        try:
            self.delete()
        except ClientError as ex:
            if self._boto3_error_match(ex, ERROR_S3_NOT_FOUND):
                if not missing_ok:
                    raise
            else:
                raise

    def delete_by_key(
            self,
            key: Union[str, PurePosixPath],
            version_id: str = None,
    ):
        warnings.warn(
            'The `delete_by_key` method is deprecated; use `delete` instead.',
            DeprecationWarning,
            stacklevel=2,
        )
        self.delete(key, version_id=version_id)

    def list_objects(self, key: Optional[Union[str, PurePosixPath]] = None, ) -> 'BucketObjectsCollection':
        key = self._get_key(key)
        try:
            collection = self.resource.Bucket(self.bucket_name).objects.filter(Prefix=key)
        except ClientError as ex:
            if self._boto3_error_match(ex, ERROR_S3_NOT_FOUND):
                raise S3ClientError(f"{self} with key={key} does not exist", ex)
            else:
                raise S3ClientError(f"{self} with key={key} list_objects yielded error {ex}", ex)
        return collection

    def find_objects(self, key: Union[str, PurePosixPath] = None) -> 'BucketObjectsCollection':
        warnings.warn(
            'The `find_objects` method is deprecated; use `list_objects` instead.',
            DeprecationWarning,
            stacklevel=2,
        )
        return self.list_objects(key=key)

    def list_object_keys(self, key: Optional[Union[str, PurePosixPath]] = None) -> List[str]:
        obj_collection = self.list_objects(key)
        return [obj.key for obj in obj_collection]

    def list_object_paths(self, key: Optional[Union[str, PurePosixPath]] = None) -> List[PurePosixPath]:
        """
        Return the relative paths of objects contained in the in/under this object
        or, if provided, under the object + provided key parameter.
        :param key:
            The
        """
        resolved_key = self._get_key(key)
        return [PurePosixPath(obj_key).relative_to(resolved_key) for obj_key in self.list_object_keys(key)]

    # noinspection SpellCheckingInspection
    def iterdir(self) -> Iterable['S3_Bucket_Key']:
        """
        Return the S3_Bucket_Key objects contained in the in/under this object.
        """
        return [self / key for key in self.list_object_paths()]

    @staticmethod
    def _path_to_key(path: PurePosixPath):
        if path.name == '' and path.parent == PurePosixPath('.'):
            return ''
        else:
            return str(path)

    @property
    def parent(self):
        key = PurePosixPath(self._get_key()).parent
        return self._factory(S3_Bucket_Key, key=self._path_to_key(key))

    @property
    def parents(self):
        return [self._factory(S3_Bucket_Key, key=self._path_to_key(key))
                for key in PurePosixPath(self._get_key()).parents
                ]

    @property
    def parts(self):
        key = PurePosixPath(self._get_key())
        return [self.bucket_name].extend(key.parts)

    @property
    def name(self):
        key = PurePosixPath(self._get_key())
        return key.name

    @property
    def suffix(self):
        key = PurePosixPath(self._get_key())
        return key.suffix

    @property
    def suffixes(self):
        key = PurePosixPath(self._get_key())
        return key.suffixes

    @property
    def stem(self):
        key = PurePosixPath(self._get_key())
        return key.stem

    def is_relative_to(self, other: 'S3_Bucket'):
        if self.bucket_name != other.bucket_name:
            return False
        else:
            key = PurePosixPath(self._get_key())
            other_key = PurePosixPath(other._get_key())
            return key.relative_to(other_key)

    def with_name(self, name: str):
        key = PurePosixPath(self._get_key())
        return self._build_s3_bucket_key(str(key.with_name(name)))

    def with_stem(self, stem: str):
        key = PurePosixPath(self._get_key())
        return self._build_s3_bucket_key(str(key.with_stem(stem)))

    def with_suffix(self, suffix: str):
        key = PurePosixPath(self._get_key())
        return self._build_s3_bucket_key(str(key.with_suffix(suffix)))

    def content_type(self) -> str:
        s3_obj = self.get_object()
        val = s3_obj.get()['ContentType']
        return val

    def is_file(self):
        try:
            return self.content_type() != 'application/x-directory'
        except ClientError as ex:
            if self._boto3_error_match(ex, ERROR_S3_NOT_FOUND):
                return False
            raise

    # Note: There is no really useful & consistent way to implement id_dir on S3
    # A good investigation related to this is here:
    # https://www.tecracer.com/blog/2023/01/what-are-the-folders-in-the-s3-console.html

    def __truediv__(
            self, other: Union[str, PurePath]
    ) -> 'S3_Bucket_Key':
        key = self._get_key(other)
        return self._build_s3_bucket_key(key)

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


# noinspection PyPep8Naming
class S3_Bucket_Key(S3_Bucket):
    """
    Represents a unique file (key) within an S3 bucket.
    Similar to S3_Bucket but the key is required
    """
    key: str

    # Note the order of decorators matters!
    # noinspection PyMethodParameters,PyNestedDecorators
    @field_validator('key')
    @classmethod
    def validate_key(cls, v):
        # Handle pathlib values
        if not isinstance(v, str):
            v = str(v)
        if len(v) == 0:
            raise ConfigError(f"Zero length string not a valid key")
        return v

    def upload_specified_file(
            self,
            local_filename: Union[str, PurePosixPath],
            extra_args: Optional[dict] = None,
            transfer_config: Optional[TransferConfig] = None,
    ):
        warnings.warn(
            "The `upload_folder_file` method is deprecated; use `my_bucket_key.upload_file() instead",
            DeprecationWarning,
            stacklevel=2,
        )
        super().upload_file(
            local_filename=local_filename,
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
        warnings.warn(
            "The `download_specified_file` method is deprecated; use `my_bucket_key.download_file() instead",
            DeprecationWarning,
            stacklevel=2,
        )
        super().download_file(
            local_filename=local_filename,
            extra_args=extra_args,
            transfer_config=transfer_config,
            create_parents=create_parents,
        )


# noinspection PyPep8Naming
class S3_Bucket_Folder(S3_Bucket):
    """
        Represents a folder within an S3 bucket.
    """
    folder: str

    # Note the order of decorators matters!
    # noinspection PyMethodParameters,PyNestedDecorators
    @field_validator('folder')
    @classmethod
    def validate_folder(cls, v):
        # Handle pathlib values
        if not isinstance(v, str):
            v = str(v)
        if len(v) == 0:
            raise ValueError(f"Zero length string not a valid folder")
        return v

    def _get_key(self, extra_key: Optional[Union[str, PurePosixPath]] = None) -> str:
        if self._non_blank_key(extra_key):
            return str(PurePosixPath(self.folder) / extra_key)
        else:
            return self.folder

    def upload_folder_file(
            self,
            local_filename: Union[str, Path],
            key_suffix: Union[str, PurePosixPath],
            extra_args: Optional[dict] = None,
            transfer_config: Optional[TransferConfig] = None,
    ):
        """
        Differs from upload_file in that it requires a key_suffix to add after the folder name
        """
        warnings.warn(
            "The `upload_folder_file` method is deprecated; use `(my_folder / key_suffix).download_file() instead",
            DeprecationWarning,
            stacklevel=2,
        )

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
        """
        Differs from download_file in that it requires a key_suffix to add after the folder name
        """
        warnings.warn(
            "The `download_folder_file` method is deprecated; use `(my_folder / key_suffix).upload_file() instead",
            DeprecationWarning,
            stacklevel=2,
        )

        full_key = PurePosixPath(self.folder, key_suffix)
        super().download_file(
            key=full_key,
            local_filename=local_filename,
            extra_args=extra_args,
            transfer_config=transfer_config,
            create_parents=create_parents,
        )


# noinspection PyPep8Naming
class S3_Bucket_Folder_File(S3_Bucket_Folder):
    """
        Represents a unique folder & file within an S3 bucket.
        Similar to S3_Bucket_Key but uses folder + file_name instead of a single key.
    """
    file_name: str

    # Note the order of decorators matters!
    # noinspection PyNestedDecorators
    @field_validator('file_name')
    @classmethod
    def validate_file_name(cls, v):
        # Handle pathlib values
        if not isinstance(v, str):
            v = str(v)
        if len(v) == 0:
            raise ConfigError(f"Zero length string not a valid file_name")
        return v

    def _get_key(self, extra_key: Optional[Union[str, PurePosixPath]] = None) -> str:
        if self._non_blank_key(extra_key):
            return str(PurePosixPath(self.folder) / self.file_name / extra_key)
        else:
            return str(PurePosixPath(self.folder) / self.file_name)

    def upload_specified_file(
        self,
        local_filename: Union[str, PurePosixPath],
        extra_args: Optional[dict] = None,
        transfer_config: Optional[TransferConfig] = None,
    ):
        warnings.warn(
            "The `upload_folder_file` method is deprecated; use `my_folder_file.upload_file() instead",
            DeprecationWarning,
            stacklevel=2,
        )

        super().upload_file(
            local_filename=local_filename,
            extra_args=extra_args,
            transfer_config=transfer_config,
        )

    def download_specified_file(
        self,
        local_filename: Union[str, PurePosixPath],
        extra_args: Optional[dict] = None,
        transfer_config: Optional[TransferConfig] = None,
    ):
        warnings.warn(
            "The `download_specified_file` method is deprecated; use `my_folder_file.download_file() instead",
            DeprecationWarning,
            stacklevel=2,
        )

        super().download_file(
            local_filename=local_filename,
            extra_args=extra_args,
            transfer_config=transfer_config,
        )
