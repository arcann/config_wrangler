import io
import logging
import warnings
from datetime import datetime, timezone
from enum import auto, Enum
from functools import lru_cache
from pathlib import PurePosixPath, Path, PurePath
from typing import *

from config_wrangler.config_exception import ConfigError
from config_wrangler.config_templates.aws.aws_session import AWS_Session
from pydantic import field_validator, PrivateAttr

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
    # https://pypi.org/project/mypy-boto3-s3/#how-to-install
    from mypy_boto3_s3.service_resource import Bucket
    from mypy_boto3_s3.service_resource import Object
    from mypy_boto3_s3.service_resource import ObjectVersion
    from mypy_boto3_s3.service_resource import ObjectSummary
    from mypy_boto3_s3.service_resource import BucketObjectsCollection
    from mypy_boto3_s3.service_resource import S3ServiceResource

# NOTE: If you are not seeing boto3-stubs code completion in Intellij-based IDEs,
#       please increase the intellisense filesize limit
#       e.g `idea.max.intellisense.filesize=20000` in IDE custom properties
#       (Help > Edit Custom Properties), then restart.

local_timezone = datetime.now(timezone.utc).astimezone().tzinfo


class OverwriteModes(Enum):
    """
    Enumeration of file overwrite behavior modes for S3 operations.

    Attributes
    ----------
    ALWAYS_OVERWRITE : auto
        Always overwrite the target file regardless of timestamps or sizes.
    OVERWRITE_OLDER : auto
        Only overwrite if source is newer or sizes differ.
    NEVER_OVERWRITE : auto
        Never overwrite existing files.
    """
    ALWAYS_OVERWRITE = auto()
    OVERWRITE_OLDER = auto()
    NEVER_OVERWRITE = auto()


class S3ClientError(ClientError):
    """
    Custom exception for S3 client errors with enhanced error context.

    Wraps boto3 ClientError exceptions with additional context while preserving
    the original error response and operation name.

    Parameters
    ----------
    message : str
        Descriptive error message.
    original_error : Optional[ClientError]
        Original boto3 ClientError, if available.
    """
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
    """
    Provides pathlib-like interface for AWS S3 bucket operations.

    Extends :class:`~config_wrangler.config_templates.aws.aws_session.AWS_Session`
    to provide file-system-like operations for S3 buckets, including upload, download,
    listing, and manipulation of S3 objects.

    Attributes
    ----------
    bucket_name : str
        The name of the S3 bucket.
    key : str | None, optional
        The S3 object key (path within bucket). Default is None.
    treat_as_folder : bool, optional
        Whether to treat the key as a folder prefix. Default is False.
    OverwriteModes : ClassVar[type[OverwriteModes]]
        Reference to :class:`OverwriteModes` enum for controlling overwrite behavior.

    Examples
    --------
    >>> bucket = S3_Bucket(bucket_name='my-bucket')
    >>> bucket.exists('path/to/file.txt')
    True
    >>> file_obj = bucket / 'path/to/file.txt'
    >>> file_obj.download_file(local_filename='local_file.txt')
    """
    bucket_name: str  #: The name of the S3 bucket
    key: str | None = None  #: The S3 object key (path within bucket)
    treat_as_folder: bool = False  #: Whether to treat the key as a folder prefix

    _service: str = PrivateAttr(default='s3')
    _object_cache: dict[str, 'Object | ObjectVersion'] = PrivateAttr(default=None)

    OverwriteModes: ClassVar[type[OverwriteModes]] = OverwriteModes

    def __str__(self):
        """
        Return S3 URI string representation.

        Returns
        -------
        str
            S3 URI in format s3://bucket_name/key or s3://bucket_name if no key.
        """
        key = self._get_key()
        if key == '':
            return f"s3://{self.bucket_name}"
        else:
            return f"s3://{self.bucket_name}/{key}"

    def __repr__(self):
        """
        Return unambiguous string representation for debugging.

        Returns
        -------
        str
            String showing bucket_name, key, and treat_as_folder attributes.
        """
        return f"S3_Bucket(bucket_name={self.bucket_name}, {self.key=}. {self.treat_as_folder=})"

    def __hash__(self):
        """
        Return hash of the S3 URI string.

        Returns
        -------
        int
            Hash value based on string representation.
        """
        return hash(str(self))

    def __eq__(self, other) -> bool:
        """
        Compare equality based on bucket_name and key.

        Parameters
        ----------
        other : S3_Bucket
            Another S3_Bucket instance to compare with.

        Returns
        -------
        bool
            True if bucket_name and key match, False otherwise.
        """
        if self.bucket_name != other.bucket_name:
            return False
        if self.key != other.key:
            return False
        return True

    @property
    def resource(self) -> 'S3ServiceResource':
        """
        Get the boto3 S3 service resource.

        Returns
        -------
        S3ServiceResource
            The boto3 S3 service resource.
        """
        return super().resource

    @property
    def client(self) -> 'S3Client':
        """
        Get the boto3 S3 client.

        Returns
        -------
        S3Client
            The boto3 S3 client.
        """
        return super().client

    def get_bucket_region_name(self) -> str:
        """
        Get the AWS region name where the bucket is located.

        Returns
        -------
        str
            AWS region name (e.g., 'us-east-1', 'us-west-2').

        Notes
        -----
        Buckets in Region us-east-1 have a LocationConstraint of null.
        """
        region = self.client.get_bucket_location(Bucket=self.bucket_name)['LocationConstraint']
        # Buckets in Region us-east-1 have a LocationConstraint of null
        if region is None:
            region = 'us-east-1'
        return region

    @staticmethod
    def _boto3_error(ex: ClientError) -> str:
        """
        Extract the error code from a boto3 ClientError.

        Parameters
        ----------
        ex : ClientError
            The boto3 ClientError exception.

        Returns
        -------
        str
            The error code string.
        """
        # noinspection PyTypeChecker
        return ex.response.get('Error', {}).get('Code')

    @staticmethod
    def _boto3_error_match(ex: ClientError, error_set: Set[str]) -> bool:
        """
        Check if a ClientError matches any error code in a set.

        Parameters
        ----------
        ex : ClientError
            The boto3 ClientError exception.
        error_set : Set[str]
            Set of error codes to match against.

        Returns
        -------
        bool
            True if the error code is in the error_set, False otherwise.
        """
        return S3_Bucket._boto3_error(ex) in error_set

    def get_boto3_bucket(self) -> 'Bucket':
        """
        Get the boto3 Bucket resource object.

        Returns
        -------
        Bucket
            The boto3 Bucket resource.

        Raises
        ------
        ClientError
            If the bucket does not exist (error code NoSuchBucket).
        """
        # Might raise error code NoSuchBucket
        return self.resource.Bucket(self.bucket_name)

    @staticmethod
    @lru_cache(maxsize=128)
    def _get_bucket_region(client, bucket_name) -> str:
        """
        Get the region name for a bucket (cached).

        Parameters
        ----------
        client : S3Client
            The boto3 S3 client.
        bucket_name : str
            The name of the S3 bucket.

        Returns
        -------
        str
            AWS region name where the bucket is located.

        Notes
        -----
        If you don't specify a Region, when the bucket is created it will have used the
        US East (N. Virginia) Region (us-east-1). So this method defaults to that if it
        does not find a LocationConstraint.
        """
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
            This can differ from the region_name attribute specified when constructing this class
            for example via a config file.
            That region_name attribute is used for establishing the AWS session.
        NOTE 2:
            If you don't specify a Region, when the bucket is created it will have used the
            US East (N. Virginia) Region (us-east-1). So this method defaults to that if it
            does not find a LocationConstraint.
        """
        return S3_Bucket._get_bucket_region(self.client, self.bucket_name)

    @staticmethod
    def _non_blank_key(key: str | PurePosixPath | None) -> bool:
        """
        Check if a key is non-blank (not None, empty string, or '/').

        Parameters
        ----------
        key : str | PurePosixPath | None
            The key to check.

        Returns
        -------
        bool
            True if the key is non-blank, False otherwise.
        """
        if key is None:
            return False

        key_str = str(key).strip()
        if key is None or key_str in {'', '/'}:
            return False
        else:
            return True

    @staticmethod
    def _is_blank_key(key: str | PurePosixPath | None) -> bool:
        """
        Check if a key is blank (None, empty string, or '/').

        Parameters
        ----------
        key : str | PurePosixPath | None
            The key to check.

        Returns
        -------
        bool
            True if the key is blank, False otherwise.
        """
        return not S3_Bucket._non_blank_key(key)

    def _get_key(self, extra_key: Optional[Union[str, PurePosixPath]] = None) -> str:
        """
        Construct the full S3 key from the instance key and an optional extra key.

        Parameters
        ----------
        extra_key : str | PurePosixPath | None, optional
            Additional key component to append to the instance key.

        Returns
        -------
        str
            The complete S3 key string.
        """
        if self._is_blank_key(extra_key):
            if self.key == '/':
                key = ''
            elif self._is_blank_key(self.key):
                key = ''
            else:
                assert self.key is not None
                key = str(self.key)
        else:
            if self._is_blank_key(self.key):
                key = extra_key
            else:
                assert self.key is not None
                key = str(PurePosixPath(self.key) / extra_key)

        # noinspection PyTypeChecker
        return key

    class CompareResult(Enum):
        """
        Enumeration of file comparison results between S3 and local files.

        Attributes
        ----------
        DIFFERENT_SIZE : auto
            Files have different sizes.
        LOCAL_NEWER : auto
            Local file has a newer modification timestamp.
        SAME_TIMES : auto
            Files have identical modification timestamps.
        LOCAL_OLDER : auto
            Local file has an older modification timestamp.
        """
        DIFFERENT_SIZE = auto()
        LOCAL_NEWER = auto()
        SAME_TIMES = auto()
        LOCAL_OLDER = auto()

    @staticmethod
    def _compare_object_to_file(
            bucket_object: 'Union[Object, ObjectSummary]',
            local_filename: Path,
    ) -> CompareResult:
        """
        Compare an S3 object to a local file by size and modification time.

        Parameters
        ----------
        bucket_object : Object | ObjectSummary
            The S3 object to compare.
        local_filename : Path
            Path to the local file to compare against.

        Returns
        -------
        CompareResult
            The comparison result indicating size differences or relative age.
        """
        s3_last_modified = bucket_object.last_modified
        try:
            # noinspection PyUnresolvedReferences
            s3_file_size = bucket_object.content_length
        except AttributeError:
            # noinspection PyUnresolvedReferences
            s3_file_size = bucket_object.size

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
        """
        Upload a local file to S3.

        Parameters
        ----------
        local_filename : str | Path
            The local file to upload.
        key : str | PurePosixPath | None, optional
            S3 key to upload to. If None, uses the instance key.
        extra_args : dict | None, optional
            Extra arguments to pass to boto3 upload_file (e.g., metadata, ACL).
        transfer_config : TransferConfig | None, optional
            Transfer configuration for the upload. Defaults to 5GB multipart threshold.
        overwrite_mode : OverwriteModes, optional
            Controls overwrite behavior. Default is ALWAYS_OVERWRITE.
        """
        if transfer_config is None:
            transfer_config = TransferConfig(multipart_threshold=5 * (1024**3))  # 5 GB

        if overwrite_mode == OverwriteModes.ALWAYS_OVERWRITE:
            do_upload = True
        else:
            try:
                key = self._get_key(key)
                bucket_key = self / key
                if overwrite_mode == OverwriteModes.NEVER_OVERWRITE:
                    do_upload = False
                else:
                    local_filename = Path(local_filename)
                    compare_result = bucket_key.compare_to_file(local_filename)
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
        """
        Open the S3 object as a file-like object for reading.

        Parameters
        ----------
        mode : str, optional
            File mode ('r' for text, 'rb' for binary). Default is 'r'.
        encoding : str | None, optional
            Text encoding (for text mode only).
        errors : str | None, optional
            Error handling strategy for encoding (for text mode only).

        Returns
        -------
        io.IOBase
            File-like object (TextIOWrapper for text mode, BufferedReader for binary).

        Raises
        ------
        ValueError
            If mode is empty or doesn't start with 'r' (only read mode is supported).
        """
        if mode is None or len(mode) == 0:
            raise ValueError('open mode required')
        if mode[0] != 'r':
            raise ValueError('S3 open mode only supports read (r, rt, rb)')

        as_text = True
        if len(mode) > 1:
            if mode[1] == 'b':
                as_text = False

        body: StreamingBody = self.get_object().get()['Body']
        # noinspection PyProtectedMember,PyTypeChecker,PyUnresolvedReferences
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
        """
        Read the S3 object contents as bytes.

        Returns
        -------
        bytes
            The complete file contents as bytes.
        """
        with self.open('rb') as f:
            return f.read()

    def read_text(self, encoding='utf-8', errors=None) -> str:
        """
        Read the S3 object contents as text.

        Parameters
        ----------
        encoding : str, optional
            Text encoding. Default is 'utf-8'.
        errors : str | None, optional
            Error handling strategy for encoding.

        Returns
        -------
        str
            The complete file contents as a string.
        """
        with self.open('rb', encoding=encoding, errors=errors) as f:
            return f.read()

    def copy_to(
            self,
            target: Union[str, 'S3_Bucket_Key'],
            version_id: str | None = None,
    ):
        """
        Copy this S3 object to another S3 location.

        Parameters
        ----------
        target : str | S3_Bucket_Key
            Target S3 location (URI string or :class:`S3_Bucket_Key` instance).
        version_id : str | None, optional
            Specific version ID to copy. If None, copies the latest version.
        """
        if isinstance(target, str):
            target = self._build_s3_bucket_key(target)
        self_key = self._get_key()
        # noinspection PyTypeChecker
        self.client.copy_object(
            Bucket=target.bucket_name,
            Key=target.key,
            CopySource=dict(
                Bucket=self.bucket_name,
                Key=self_key,
                VersionId=version_id,
            )
        )

    def rename(self, target: str):
        """
        Rename (move) this S3 object to a new key.

        Parameters
        ----------
        target : str
            Target S3 key or URI.

        Notes
        -----
        This copies the object to the new location then deletes the original.
        """
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
    ):
        """
        Download an S3 object to a local file.

        Parameters
        ----------
        local_filename : Path | str
            Path where the downloaded file will be saved.
        key : str | PurePosixPath | None, optional
            S3 key to download. If None, uses the instance key.
        extra_args : dict | None, optional
            Extra arguments to pass to boto3 download_file.
        transfer_config : TransferConfig | None, optional
            Transfer configuration for the download.
        create_parents : bool, optional
            Whether to create parent directories. Default is True.
        overwrite_mode : OverwriteModes, optional
            Controls overwrite behavior. Default is OVERWRITE_OLDER.

        Raises
        ------
        S3ClientError
            If the S3 object does not exist or download fails.
        ValueError
            If a non-blank key is not specified for the download.
        """
        if self._non_blank_key(key):
            assert key is not None
            file_obj = self / key
            file_obj.download_file(
                local_filename=local_filename,
                extra_args=extra_args,
                transfer_config=transfer_config,
                create_parents=create_parents,
                overwrite_mode=overwrite_mode,
            )
        else:
            log = logging.getLogger(f"{__name__}.download_file")

            if isinstance(self, S3_Bucket_Key_Version):
                s3_file: S3_Bucket_Key_Version = self
            elif isinstance(self, S3_Bucket_Key):
                s3_file: S3_Bucket_Key = self
            elif isinstance(self, S3_Bucket_Folder_File):
                s3_file = self._build_s3_bucket_key(self._get_key())
            else:
                raise ValueError(f"Need to specify a non-blank key for download_file from {type(self)}")

            assert isinstance(s3_file, S3_Bucket_Key)

            local_path = Path(local_filename)
            if create_parents:
                local_path.parent.mkdir(parents=True, exist_ok=True)

            try:
                if overwrite_mode in {OverwriteModes.OVERWRITE_OLDER, OverwriteModes.NEVER_OVERWRITE}:
                    if local_path.exists():
                        if overwrite_mode == OverwriteModes.NEVER_OVERWRITE:
                            do_download = False
                            log.info(f"{self} download to {local_path} skipped since file exists and mode = {overwrite_mode}")
                        else:  # Check ages and size

                            compare_result = s3_file.compare_to_file(local_path)

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
            treat_as_folder: bool | None = None,
            extra_args: Optional[dict] = None,
            transfer_config: Optional[TransferConfig] = None,
            create_parents: bool = True,
            overwrite_mode: OverwriteModes = OverwriteModes.OVERWRITE_OLDER,
    ) -> Iterable[Path]:
        """
        Download multiple S3 objects under a key prefix to a local directory.

        Parameters
        ----------
        local_path : str | Path
            Local directory path where files will be downloaded.
        key : str | PurePosixPath | None, optional
            S3 key prefix. If None, uses the instance key.
        treat_as_folder : bool | None, optional
            Whether to treat the key as a folder prefix. If None, uses instance setting.
        extra_args : dict | None, optional
            Extra arguments to pass to boto3 download_file.
        transfer_config : TransferConfig | None, optional
            Transfer configuration for downloads.
        create_parents : bool, optional
            Whether to create parent directories. Default is True.
        overwrite_mode : OverwriteModes, optional
            Controls overwrite behavior. Default is OVERWRITE_OLDER.

        Returns
        -------
        Iterable[Path]
            List of local file paths that were downloaded.
        """
        if self._non_blank_key(key):
            assert key is not None
            file_obj = self / key
            return file_obj.download_files(
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
            for s3_object in self.list_objects(treat_as_folder=treat_as_folder):
                assert s3_object.key is not None
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
                )
            return results

    def head_object(
            self,
            key: Optional[Union[str, PurePosixPath]] = None,
            version_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Check if an S3 object exists.

        Parameters
        ----------
        key : str | PurePosixPath | None, optional
            S3 key to check. If None, uses the instance key.
        version_id : str | None, optional
            Specific version ID to check. If None, checks the latest version.

        Returns
        -------
        dict[str, Any]
            Dictionary as returned by boto3 head_object

        Raises
        ------
        ClientError
            If there's an error
        """
        key = self._get_key(key)

        extra_args = {}
        if version_id is not None:
            extra_args['VersionId'] = version_id

        # noinspection PyTypeChecker
        return self.client.head_object(Bucket=self.bucket_name, Key=str(key), **extra_args)

    def exists(
            self,
            key: Optional[Union[str, PurePosixPath]] = None,
            version_id: str | None = None,
    ) -> bool:
        """
        Check if an S3 object exists.

        Parameters
        ----------
        key : str | PurePosixPath | None, optional
            S3 key to check. If None, uses the instance key.
        version_id : str | None, optional
            Specific version ID to check. If None, checks the latest version.

        Returns
        -------
        bool
            True if the object exists, False otherwise.

        Raises
        ------
        ClientError
            If there's an error other than 404/NoSuchKey.
        """
        try:
            self.head_object(key=key, version_id=version_id)
            return True
        except ClientError as ex:
            if self._boto3_error_match(ex, ERROR_S3_NOT_FOUND):
                return False
            else:
                raise

    def key_exists(self, key: Union[str, PurePosixPath]) -> bool:
        """
        Check if an S3 object exists at the specified key.

        .. deprecated::
            Use :meth:`exists` instead.

        Parameters
        ----------
        key : str | PurePosixPath
            S3 key to check.

        Returns
        -------
        bool
            True if the object exists, False otherwise.
        """
        warnings.warn(
            'The `key_exists` method is deprecated; use `exists` instead.',
            DeprecationWarning,
            stacklevel=2,
        )
        return self.exists(key)

    def get_object_uncached(
            self,
            key: Optional[Union[str, PurePosixPath]] = None,
            version_id: str | None = None,
    ) -> 'Object | ObjectVersion':
        """
        Get a boto3 Object or ObjectVersion resource without caching.

        Parameters
        ----------
        key : str | PurePosixPath | None, optional
            S3 key. If None, uses the instance key.
        version_id : str | None, optional
            Specific version ID. If None, returns the latest version Object.

        Returns
        -------
        Object | ObjectVersion
            The boto3 Object or ObjectVersion resource.
        """
        key = self._get_key(key)
        obj = self.resource.Object(self.bucket_name, str(key))
        if version_id is None:
            return obj
        else:
            return obj.Version(version_id)

    def get_object(
            self,
            key: Optional[Union[str, PurePosixPath]] = None,
            version_id: str | None = None,
    ) -> 'Object | ObjectVersion':
        """
        Get a boto3 Object or ObjectVersion resource with caching.

        Parameters
        ----------
        key : str | PurePosixPath | None, optional
            S3 key. If None, uses the instance key.
        version_id : str | None, optional
            Specific version ID. If None, returns the latest version Object.

        Returns
        -------
        Object | ObjectVersion
            The boto3 Object or ObjectVersion resource.
        """
        if self._object_cache is None:
            self._object_cache = {}
        hash_key = f"{self.bucket_name}:{key},version={version_id}"
        try:
            return self._object_cache[hash_key]
        except KeyError:
            s3_object = self.get_object_uncached(key, version_id=version_id)
            self._object_cache[hash_key] = s3_object
            return s3_object

    def get_s3_bucket_key(
            self,
            key: Optional[Union[str, PurePosixPath]] = None,
    ) -> 'S3_Bucket_Key':
        """
        Get an :class:`S3_Bucket_Key` instance for the specified key.

        Parameters
        ----------
        key : str | PurePosixPath | None, optional
            S3 key. If None, uses the instance key.

        Returns
        -------
        S3_Bucket_Key
            S3_Bucket_Key instance representing the key.
        """
        key = self._get_key(key)
        return self._build_s3_bucket_key(key, treat_as_folder=False)

    def delete(
            self,
            key: Optional[Union[str, PurePosixPath]] = None,
            version_id: str | None = None,
    ):
        """
        Delete an S3 object.

        Parameters
        ----------
        key : str | PurePosixPath | None, optional
            S3 key to delete. If None, uses the instance key.
        version_id : str | None, optional
            Specific version ID to delete. If None, deletes the latest version.
        """
        key = self._get_key(key)
        kwargs = {
            'Bucket': self.bucket_name,
            'Key': key,
        }
        if version_id is not None:
            kwargs['VersionId'] = version_id
        self.client.delete_object(**kwargs)

    def unlink(
            self,
            key: Optional[Union[str, PurePosixPath]] = None,
            version_id: str | None = None,
            missing_ok=False,
    ):
        """
        Delete an S3 object (pathlib-style interface).

        Parameters
        ----------
        key : str | PurePosixPath | None, optional
            S3 key to delete. If None, uses the instance key.
        version_id : str | None, optional
            Specific version ID to delete. If None, deletes the latest version.
        missing_ok : bool, optional
            If True, don't raise an error if the object doesn't exist. Default is False.

        Raises
        ------
        ClientError
            If the object doesn't exist and missing_ok is False, or other errors occur.
        """
        try:
            self.delete(key=key, version_id=version_id)
        except ClientError as ex:
            if self._boto3_error_match(ex, ERROR_S3_NOT_FOUND):
                if not missing_ok:
                    raise
            else:
                raise

    def delete_by_key(
            self,
            key: Union[str, PurePosixPath],
            version_id: str | None = None,
    ):
        """
        Delete an S3 object by key.

        .. deprecated::
            Use :meth:`delete` instead.

        Parameters
        ----------
        key : str | PurePosixPath
            S3 key to delete.
        version_id : str | None, optional
            Specific version ID to delete.
        """
        warnings.warn(
            'The `delete_by_key` method is deprecated; use `delete` instead.',
            DeprecationWarning,
            stacklevel=2,
        )
        self.delete(key, version_id=version_id)

    def list_objects(
            self,
            key: Optional[Union[str, PurePosixPath]] = None,
            treat_as_folder: bool | None = None,
    ) -> 'BucketObjectsCollection':
        """
        List S3 objects under a key prefix.

        Parameters
        ----------
        key : str | PurePosixPath | None, optional
            S3 key prefix. If None, uses the instance key.
        treat_as_folder : bool | None, optional
            Whether to treat the key as a folder by appending '/'. If None, uses instance setting.

        Returns
        -------
        BucketObjectsCollection
            Collection of S3 ObjectSummary objects matching the prefix.

        Raises
        ------
        S3ClientError
            If the bucket or key doesn't exist, or other errors occur.
        """
        log = logging.getLogger(f"{__name__}.list_objects")
        if treat_as_folder is None and key is not None:
            # If directly provided a key string, use it as is
            treat_as_folder = False
            log.debug(f"Using provided key {key}, defaulting treat_as_folder = False")
        key = self._get_key(key)
        if treat_as_folder is None:
            log.debug(f"Defaulting treat_as_folder to setting value {self.treat_as_folder}")
            treat_as_folder = self.treat_as_folder
        if key == '/':
            key = ''
        if treat_as_folder:
            if key != '' and not key.endswith('/'):
                key = f"{key}/"
                log.debug(f"treat_as_folder True, adding / to the end = {key}")
        try:
            collection = self.resource.Bucket(self.bucket_name).objects.filter(Prefix=key)
        except ClientError as ex:
            if self._boto3_error_match(ex, ERROR_S3_NOT_FOUND):
                raise S3ClientError(f"{self} with key={key} does not exist", ex)
            else:
                raise S3ClientError(f"{self} with key={key} list_objects yielded error {ex}", ex)
        return collection

    def find_objects(
            self,
            key: str | PurePosixPath | None = None,
    ) -> 'BucketObjectsCollection':
        """
        List S3 objects under a key prefix.

        .. deprecated::
            Use :meth:`list_objects` instead.

        Parameters
        ----------
        key : str | PurePosixPath | None, optional
            S3 key prefix.

        Returns
        -------
        BucketObjectsCollection
            Collection of S3 ObjectSummary objects.
        """
        warnings.warn(
            'The `find_objects` method is deprecated; use `list_objects` instead.',
            DeprecationWarning,
            stacklevel=2,
        )
        return self.list_objects(key=key)

    def list_object_keys(
            self,
            key: Optional[Union[str, PurePosixPath]] = None,
            treat_as_folder: bool | None = None,
    ) -> List[str]:
        """
        List S3 object keys under a key prefix.

        Parameters
        ----------
        key : str | PurePosixPath | None, optional
            S3 key prefix. If None, uses the instance key.
        treat_as_folder : bool | None, optional
            Whether to treat the key as a folder. If None, uses instance setting.

        Returns
        -------
        List[str]
            List of S3 object keys.
        """
        obj_collection = self.list_objects(key, treat_as_folder=treat_as_folder)
        return [obj.key for obj in obj_collection]

    def list_object_paths(
            self,
            key: Optional[Union[str, PurePosixPath]] = None,
            treat_as_folder: bool | None = None,
    ) -> List[PurePosixPath]:
        """
        Return the relative paths of objects contained in/under this object.

        Parameters
        ----------
        key : str | PurePosixPath | None, optional
            S3 key prefix. If None, uses the instance key.
        treat_as_folder : bool | None, optional
            Whether to treat the key as a folder. If None, uses instance setting.

        Returns
        -------
        List[PurePosixPath]
            List of relative paths (PurePosixPath) of objects under the key prefix.
        """
        resolved_key = self._get_key(key)
        return [
            PurePosixPath(obj_key).relative_to(resolved_key)
            for obj_key in self.list_object_keys(key, treat_as_folder=treat_as_folder)
        ]

    # noinspection SpellCheckingInspection
    def iterdir(self) -> Iterable['S3_Bucket_Key']:
        """
        Return the S3_Bucket_Key objects contained in the in/under this object.
        """
        for obj in self.list_objects(treat_as_folder=True):
            bucket_key = self._build_s3_bucket_key(key=obj.key)
            bucket_key._last_modified = obj.last_modified
            bucket_key._size = obj.size
            yield bucket_key

    @staticmethod
    def _path_to_key(path: PurePosixPath):
        """
        Convert a PurePosixPath to an S3 key string.

        Parameters
        ----------
        path : PurePosixPath
            Path to convert.

        Returns
        -------
        str
            S3 key string (empty string for root paths).
        """
        if path.name == '' and path.parent == PurePosixPath('.'):
            return ''
        else:
            return str(path)

    @property
    def parent(self):
        """
        Get the parent :class:`S3_Bucket_Key`.

        Returns
        -------
        S3_Bucket_Key
            S3_Bucket_Key representing the parent key.
        """
        key = PurePosixPath(self._get_key()).parent
        return self._factory(S3_Bucket_Key, key=self._path_to_key(key))

    @property
    def parents(self):
        """
        Get all parent :class:`S3_Bucket_Key` instances.

        Returns
        -------
        List[S3_Bucket_Key]
            List of S3_Bucket_Key instances representing all parent keys.
        """
        return [self._factory(S3_Bucket_Key, key=self._path_to_key(key))
                for key in PurePosixPath(self._get_key()).parents
                ]

    @property
    def parts(self):
        """
        Get the parts of the S3 path (bucket name + key parts).

        Returns
        -------
        List[str]
            List containing bucket name followed by key parts.
        """
        key = PurePosixPath(self._get_key())
        return [self.bucket_name].extend(key.parts)

    @property
    def name(self):
        """
        Get the final component of the S3 key.

        Returns
        -------
        str
            The file name or final path component.
        """
        key = PurePosixPath(self._get_key())
        return key.name

    @property
    def suffix(self):
        """
        Get the file extension of the S3 key.

        Returns
        -------
        str
            The file extension (e.g., '.txt', '.json').
        """
        key = PurePosixPath(self._get_key())
        return key.suffix

    @property
    def suffixes(self):
        """
        Get all file extensions of the S3 key.

        Returns
        -------
        List[str]
            List of all file extensions (e.g., ['.tar', '.gz']).
        """
        key = PurePosixPath(self._get_key())
        return key.suffixes

    @property
    def stem(self):
        """
        Get the file name without extension.

        Returns
        -------
        str
            The file name without the final extension.
        """
        key = PurePosixPath(self._get_key())
        return key.stem

    def is_relative_to(self, other: 'S3_Bucket'):
        """
        Check if this S3 path is relative to another.

        Parameters
        ----------
        other : S3_Bucket
            Another S3_Bucket instance to compare with.

        Returns
        -------
        bool
            True if this path is relative to the other path, False otherwise.
        """
        if self.bucket_name != other.bucket_name:
            return False
        else:
            key = PurePosixPath(self._get_key())
            other_key = PurePosixPath(other._get_key())
            return key.relative_to(other_key)

    def with_name(self, name: str):
        """
        Return a new :class:`S3_Bucket_Key` with the file name changed.

        Parameters
        ----------
        name : str
            The new file name.

        Returns
        -------
        S3_Bucket_Key
            New S3_Bucket_Key with the modified name.
        """
        key = PurePosixPath(self._get_key())
        return self._build_s3_bucket_key(str(key.with_name(name)))

    def with_stem(self, stem: str):
        """
        Return a new :class:`S3_Bucket_Key` with the file stem changed.

        Parameters
        ----------
        stem : str
            The new file stem (name without extension).

        Returns
        -------
        S3_Bucket_Key
            New S3_Bucket_Key with the modified stem.
        """
        key = PurePosixPath(self._get_key())
        return self._build_s3_bucket_key(str(key.with_stem(stem)))

    def with_suffix(self, suffix: str):
        """
        Return a new :class:`S3_Bucket_Key` with the file suffix changed.

        Parameters
        ----------
        suffix : str
            The new file extension (e.g., '.txt').

        Returns
        -------
        S3_Bucket_Key
            New S3_Bucket_Key with the modified suffix.
        """
        key = PurePosixPath(self._get_key())
        return self._build_s3_bucket_key(str(key.with_suffix(suffix)))

    def content_type(self) -> str:
        """
        Get the content type (MIME type) of the S3 object.

        Returns
        -------
        str
            The content type string (e.g., 'text/plain', 'application/json').
        """
        s3_obj = self.get_object()
        val = s3_obj.get()['ContentType']
        return val

    def is_file(self):
        """
        Check if this S3 object represents a file (not a directory marker).

        Returns
        -------
        bool
            True if it's a file, False if it's a directory marker or doesn't exist.

        Notes
        -----
        S3 doesn't have true directories, but some tools create directory markers
        with content type 'application/x-directory'.
        """
        try:
            return self.content_type() != 'application/x-directory'
        except ClientError as ex:
            if self._boto3_error_match(ex, ERROR_S3_NOT_FOUND):
                return False
            raise

    # Note: There is no really useful & consistent way to implement is_dir on S3
    # A good investigation related to this is here:
    # https://www.tecracer.com/blog/2023/01/what-are-the-folders-in-the-s3-console.html

    def __truediv__(
            self, other: Union[str, PurePosixPath]
    ) -> 'S3_Bucket_Key':
        """
        Join paths using the `/` operator.

        Parameters
        ----------
        other : str | PurePosixPath
            Path component to append.

        Returns
        -------
        S3_Bucket_Key
            New S3_Bucket_Key with the joined path.
        """
        key = self._get_key(other)
        return self._build_s3_bucket_key(key, treat_as_folder=True)

    # noinspection SpellCheckingInspection
    def joinpath(
        self,
        *others
    ) -> Union[
        'S3_Bucket_Key',
        'S3_Bucket_Folder'
    ]:
        """
        Join multiple path components.

        Parameters
        ----------
        *others
            Path components to join.

        Returns
        -------
        S3_Bucket_Key | S3_Bucket_Folder
            New S3 path object with all components joined.
        """
        new_path = self
        for other in others:
            new_path = new_path / other
        # noinspection PyTypeChecker
        return new_path

    def as_bucket(self) -> 'S3_Bucket':
        """
        Create a new :class:`S3_Bucket` instance with only the bucket name.

        Returns
        -------
        S3_Bucket
            S3_Bucket instance without key, folder, or file_name attributes.
        """
        return self._factory(
            S3_Bucket,
            exclude={'key', 'folder', 'file_name'},
        )

    def _build_s3_bucket_folder(self, folder: Union[str, Path]):
        """
        Create an :class:`S3_Bucket_Folder` instance.

        Parameters
        ----------
        folder : str | Path
            Folder path within the bucket.

        Returns
        -------
        S3_Bucket_Folder
            S3_Bucket_Folder instance.
        """
        return self._factory(
            S3_Bucket_Folder,
            exclude={'file_name'},
            folder=str(folder)
        )

    def _build_s3_bucket_folder_file(self, file_name: Union[str, Path], folder: Union[str, Path] | None = None):
        """
        Create an :class:`S3_Bucket_Folder_File` instance.

        Parameters
        ----------
        file_name : str | Path
            File name.
        folder : str | Path | None, optional
            Folder path. If None, uses the instance folder.

        Returns
        -------
        S3_Bucket_Folder_File
            S3_Bucket_Folder_File instance.
        """
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

    def _build_s3_bucket_key(
            self,
            key: Union[str, Path, PurePath],
            treat_as_folder: bool | None = None,
    ):
        """
        Create an :class:`S3_Bucket_Key` instance.

        Parameters
        ----------
        key : str | Path | PurePath
            S3 key string.
        treat_as_folder : bool | None, optional
            Whether to treat the key as a folder. If None, uses instance setting.

        Returns
        -------
        S3_Bucket_Key
            S3_Bucket_Key instance.
        """
        s3_key_obj = self._factory(
            S3_Bucket_Key, key=str(key), exclude={'folder', 'file_name'}
        )
        if treat_as_folder is not None:
            s3_key_obj.treat_as_folder = treat_as_folder
        return s3_key_obj


# noinspection PyPep8Naming
class S3_Bucket_Key(S3_Bucket):
    """
    Represents a unique file (key) within an S3 bucket.

    Subclass of :class:`S3_Bucket` that additionally allows a key to be specified.
    This can represent either a "folder" like key prefix or an individual S3 object (file).
    Also provides cached access to object metadata like size and modification time.

    Attributes
    ----------
    key : str
        The S3 object key (required). Must be a valid S3 key string.
    """
    key: str  #: The S3 object key (required)
    _last_modified: datetime = PrivateAttr(default=None)
    _size: int = PrivateAttr(default=None)

    # Note the order of decorators matters!
    # noinspection PyMethodParameters,PyNestedDecorators
    @field_validator('key')
    @classmethod
    def validate_key(cls, v):
        """
        Validate and convert the key to a string.

        Parameters
        ----------
        v : Any
            Key value to validate.

        Returns
        -------
        str
            Validated key string.
        """
        # Handle pathlib values
        if not isinstance(v, str):
            v = str(v)
        return v

    def __repr__(self):
        """
        Return unambiguous string representation for debugging.

        Returns
        -------
        str
            String showing bucket_name, key, and treat_as_folder attributes.
        """
        return f"S3_Bucket_Key(bucket_name={self.bucket_name}, {self.key=}. {self.treat_as_folder=})"

    def _set_attributes(self):
        """
        Fetch and cache the object's last_modified and size attributes from S3.
        """
        obj = self.get_object()
        self._last_modified = obj.last_modified
        try:
            self._size = obj.size
        except AttributeError:
            self._size = obj.content_length

    @property
    def last_modified(self) -> datetime:
        """
        Get the last modification time of the S3 object.

        Returns
        -------
        datetime
            The last modification timestamp.
        """
        if self._last_modified is None:
            self._set_attributes()
        assert self._last_modified is not None
        return self._last_modified

    @property
    def size(self) -> int:
        """
        Get the size of the S3 object in bytes.

        Returns
        -------
        int
            The object size in bytes.
        """
        if self._size is None:
            self._set_attributes()
        assert self._size is not None
        return self._size

    def compare_to_file(
            self,
            local_filename: Path,
    ) -> 'S3_Bucket.CompareResult':
        """
        Compare this S3 object to a local file.

        Parameters
        ----------
        local_filename : Path
            Path to the local file to compare against.

        Returns
        -------
        S3_Bucket.CompareResult
            The comparison result indicating size differences or relative age.
        """
        s3_last_modified = self.last_modified
        s3_file_size = self.size

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

    def iter_versions(self) -> Iterator['S3_Bucket_Key_Version']:
        """
        Iterate over all versions of this S3 object key.

        Yields S3_Bucket_Key_Version objects for each version that exists in S3.
        Versions are returned in the order provided by S3 (typically newest first).

        Raises:
            ClientError: If there's an error accessing the S3 bucket or versions.
        """
        key = self._get_key()
        try:
            paginator = self.client.get_paginator('list_object_versions')
            page_iterator = paginator.paginate(
                Bucket=self.bucket_name,
                Prefix=key,
            )

            for page in page_iterator:
                versions = page.get('Versions', [])
                for version_data in versions:
                    if version_data['Key'] == key:
                        version_id = version_data['VersionId']
                        if version_id == 'null':
                            version_id = None
                        obj = self._factory(
                            S3_Bucket_Key_Version,
                            key=key,
                            version_id=version_id,
                            is_latest=version_data.get('IsLatest', False),
                        )
                        obj._last_modified = version_data.get('LastModified')
                        obj._size = version_data.get('Size')
                        yield obj

        except ClientError as ex:
            if self._boto3_error_match(ex, ERROR_S3_NOT_FOUND):
                raise S3ClientError(f"{self} does not exist or bucket versioning not enabled", ex)
            else:
                raise S3ClientError(f"{self} iter_versions yielded error {ex}", ex)

    def latest_version(self) -> 'S3_Bucket_Key_Version':
        """
        Get the latest version of this S3 object.

        Returns
        -------
        S3_Bucket_Key_Version
            The latest version of this S3 object.

        Raises
        ------
        FileNotFoundError
            If no latest version exists or multiple latest versions are found.
        """
        latest_versions = [v for v in self.iter_versions() if v.is_latest]
        if len(latest_versions) == 0:
            raise FileNotFoundError(f"No latest version found for {self}")
        if len(latest_versions) > 1:
            raise FileNotFoundError(f"Multiple latest version found for {self}")
        return latest_versions[0]

    def version_map(self) -> dict[str, 'S3_Bucket_Key_Version']:
        """
        Get a mapping of version IDs to :class:`S3_Bucket_Key_Version` instances.

        Returns
        -------
        dict[str, S3_Bucket_Key_Version]
            Dictionary mapping version IDs to S3_Bucket_Key_Version objects.
        """
        return {v.version_id: v for v in self.iter_versions()}

    def version(self, version_id: str) -> 'S3_Bucket_Key_Version':
        """
        Get a specific version of this S3 object by version ID.

        Parameters
        ----------
        version_id : str
            The version ID to retrieve.

        Returns
        -------
        S3_Bucket_Key_Version
            The S3_Bucket_Key_Version instance for the specified version.

        Raises
        ------
        FileNotFoundError
            If the specified version ID does not exist.
        """
        version_map = self.version_map()
        try:
            return version_map[version_id]
        except KeyError:
            raise FileNotFoundError(f"No version found for {self} + version_id = {version_id}")

    def upload_specified_file(
            self,
            local_filename: Union[str, Path],
            extra_args: Optional[dict] = None,
            transfer_config: Optional[TransferConfig] = None,
    ):
        """
        Upload a local file to this S3 key.

        .. deprecated::
            Use :meth:`upload_file` instead.

        Parameters
        ----------
        local_filename : str | Path
            Path to the local file to upload.
        extra_args : dict | None, optional
            Extra arguments to pass to boto3 upload_file.
        transfer_config : TransferConfig | None, optional
            Transfer configuration for the upload.
        """
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
            local_filename: Union[str, Path],
            extra_args: Optional[dict] = None,
            transfer_config: Optional[TransferConfig] = None,
            create_parents: bool = True,
    ):
        """
        Download this S3 object to a local file.

        .. deprecated::
            Use :meth:`download_file` instead.

        Parameters
        ----------
        local_filename : str | Path
            Path where the downloaded file will be saved.
        extra_args : dict | None, optional
            Extra arguments to pass to boto3 download_file.
        transfer_config : TransferConfig | None, optional
            Transfer configuration for the download.
        create_parents : bool, optional
            Whether to create parent directories. Default is True.
        """
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
class S3_Bucket_Key_Version(S3_Bucket_Key):
    """
    Represents a specific version of an S3 object key.
    Extends S3_Bucket_Key with version_id to uniquely identify a version.
    """
    version_id: str  #: The S3 object version ID
    is_latest: bool = False  #: Whether this is the latest version
    treat_as_folder: bool = False  #: Whether to treat as a folder prefix

    @field_validator('version_id')
    @classmethod
    def validate_version_id(cls, v):
        """
        Validate and convert the version_id to a string.

        Parameters
        ----------
        v : Any
            Version ID value to validate.

        Returns
        -------
        str | None
            Validated version ID string, or None if 'null'.
        """
        if not isinstance(v, str):
            v = str(v)
        if v == 'null':
            v = None
        return v

    def __str__(self):
        """
        Return S3 URI string representation with version ID.

        Returns
        -------
        str
            S3 URI with version ID query parameter.
        """
        key = self._get_key()
        return f"s3://{self.bucket_name}/{key}?versionId={self.version_id}"

    def __repr__(self):
        """
        Return unambiguous string representation for debugging.

        Returns
        -------
        str
            String showing bucket_name, key, and version_id attributes.
        """
        return f"S3_Bucket_Key_Version(bucket_name={self.bucket_name}, {self.key=}. {self.version_id=})"

    def __eq__(self, other) -> bool:
        """
        Compare equality based on bucket_name, key, and version_id.

        Parameters
        ----------
        other : S3_Bucket_Key_Version
            Another S3_Bucket_Key_Version instance to compare with.

        Returns
        -------
        bool
            True if bucket_name, key, and version_id match, False otherwise.
        """
        if not super().__eq__(other):
            return False
        if self.version_id != other.version_id:
            return False
        return True

    def get_object_uncached(
            self,
            key: Optional[Union[str, PurePosixPath]] = None,
            version_id: str | None = None,
    ) -> 'Object | ObjectVersion':
        """
        Get the versioned object from S3 without caching.

        Parameters
        ----------
        key : str | PurePosixPath | None, optional
            Ignored for this subclass (always uses instance key).
        version_id : str | None, optional
            Version ID to retrieve. If None, uses instance version_id.

        Returns
        -------
        Object | ObjectVersion
            The boto3 ObjectVersion resource.
        """
        if version_id is None:
            return super().get_object_uncached(self.key, version_id=self.version_id)
        else:
            # Override the version_id stored in self
            return super().get_object_uncached(self.key, version_id=version_id)

    def exists(
            self,
            key: Optional[Union[str, PurePosixPath]] = None,
            version_id: str | None = None,
    ) -> bool:
        """
        Check if this specific version of the S3 object exists.

        Parameters
        ----------
        key : str | PurePosixPath | None, optional
            Ignored for this subclass (always uses instance key).
        version_id : str | None, optional
            Version ID to check. If None, uses instance version_id.

        Returns
        -------
        bool
            True if the version exists, False otherwise.
        """
        if version_id is None:
            return super().exists(self.key, version_id=self.version_id)
        else:
            # Override the version_id stored in self
            return super().exists(self.key, version_id=version_id)

    def delete(
            self,
            key: Optional[Union[str, PurePosixPath]] = None,
            version_id: str | None = None,
    ):
        """
        Delete this specific version of the S3 object.

        Parameters
        ----------
        key : str | PurePosixPath | None, optional
            Ignored for this subclass (always uses instance key).
        version_id : str | None, optional
            Version ID to delete. If None, uses instance version_id.
        """
        if version_id is None:
            super().delete(self.key, version_id=self.version_id)
        else:
            # Override the version_id stored in self
            super().delete(self.key, version_id=version_id)

    def unlink(
            self,
            key: Optional[Union[str, PurePosixPath]] = None,
            version_id: str | None = None,
            missing_ok=False,
    ):
        """
        Delete this specific version of the S3 object (pathlib-style).

        Parameters
        ----------
        key : str | PurePosixPath | None, optional
            Ignored for this subclass (always uses instance key).
        version_id : str | None, optional
            Version ID to delete. If None, uses instance version_id.
        missing_ok : bool, optional
            If True, don't raise an error if the version doesn't exist. Default is False.
        """
        if version_id is None:
            super().unlink(self.key, version_id=self.version_id, missing_ok=missing_ok)
        else:
            # Override the version_id stored in self
            super().unlink(self.key, version_id=version_id, missing_ok=missing_ok)

    def download_file(
            self,
            *,
            local_filename: Union[str, Path],
            key: Optional[Union[str, PurePosixPath]] = None,
            extra_args: Optional[dict] = None,
            transfer_config: Optional[TransferConfig] = None,
            create_parents: bool = True,
            overwrite_mode: OverwriteModes = OverwriteModes.OVERWRITE_OLDER,
    ):
        """
        Download this specific version of the S3 object to a local file.

        Parameters
        ----------
        local_filename : str | Path
            Path where the downloaded file will be saved.
        key : str | PurePosixPath | None, optional
            Ignored for this subclass.
        extra_args : dict | None, optional
            Extra arguments to pass to boto3 download_file. VersionId is automatically added.
        transfer_config : TransferConfig | None, optional
            Transfer configuration for the download.
        create_parents : bool, optional
            Whether to create parent directories. Default is True.
        overwrite_mode : OverwriteModes, optional
            Controls overwrite behavior. Default is OVERWRITE_OLDER.
        """
        if extra_args is None:
            extra_args = {}
        if 'VersionId' not in extra_args and self.version_id is not None:
            extra_args['VersionId'] = self.version_id

        super().download_file(
            local_filename=local_filename,
            key=key,
            extra_args=extra_args,
            transfer_config=transfer_config,
            create_parents=create_parents,
            overwrite_mode=overwrite_mode,
        )

    def copy_to(
            self,
            target: Union[str, 'S3_Bucket_Key'],
            version_id: str | None = None,
    ):
        """
        Copy this specific version of the S3 object to another location.

        Parameters
        ----------
        target : str | S3_Bucket_Key
            Target S3 location.
        version_id : str | None, optional
            Version ID to copy. If None, uses instance version_id.
        """
        if version_id is None:
            super().copy_to(target=target, version_id=self.version_id)
        else:
            # Override the version_id stored in self
            super().copy_to(target=target, version_id=version_id)


# noinspection PyPep8Naming
class S3_Bucket_Folder(S3_Bucket):
    """
    Represents a folder within an S3 bucket.

    Attributes
    ----------
    folder : str
        The folder path within the bucket.
    treat_as_folder : bool
        Always True for this class.
    """
    folder: str  #: The folder path within the bucket
    treat_as_folder: bool = True  #: Always treat as a folder

    # Note the order of decorators matters!
    # noinspection PyMethodParameters,PyNestedDecorators
    @field_validator('folder')
    @classmethod
    def validate_folder(cls, v):
        """
        Validate and convert the folder to a string.

        Parameters
        ----------
        v : Any
            Folder value to validate.

        Returns
        -------
        str
            Validated folder string (empty string for root folder).
        """
        # Handle pathlib values
        if not isinstance(v, str):
            v = str(v)
        if v == '/':
            # Root folder is blank key in S3
            v = ''
        return v

    def __repr__(self):
        """
        Return unambiguous string representation for debugging.

        Returns
        -------
        str
            String showing bucket_name and folder attributes.
        """
        return f"S3_Bucket_Folder(bucket_name={self.bucket_name}, {self.folder=})"

    def _get_key(self, extra_key: Optional[Union[str, PurePosixPath]] = None) -> str:
        """
        Construct the full S3 key from the folder and an optional extra key.

        Parameters
        ----------
        extra_key : str | PurePosixPath | None, optional
            Additional key component to append to the folder.

        Returns
        -------
        str
            The complete S3 key string.
        """
        folder_key = self.folder.lstrip('/')
        if self._non_blank_key(extra_key):
            return str(PurePosixPath(folder_key) / extra_key)
        else:
            return folder_key

    def upload_folder_file(
            self,
            local_filename: Union[str, Path],
            key_suffix: Union[str, PurePosixPath],
            extra_args: Optional[dict] = None,
            transfer_config: Optional[TransferConfig] = None,
    ):
        """
        Upload a local file to a key within this folder.

        .. deprecated::
            Use ``(my_folder / key_suffix).upload_file()`` instead.

        Parameters
        ----------
        local_filename : str | Path
            Path to the local file to upload.
        key_suffix : str | PurePosixPath
            Key suffix to add after the folder name.
        extra_args : dict | None, optional
            Extra arguments to pass to boto3 upload_file.
        transfer_config : TransferConfig | None, optional
            Transfer configuration for the upload.
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
        Download a file from a key within this folder.

        .. deprecated::
            Use ``(my_folder / key_suffix).download_file()`` instead.

        Parameters
        ----------
        key_suffix : str | PurePosixPath
            Key suffix to add after the folder name.
        local_filename : str | Path
            Path where the downloaded file will be saved.
        extra_args : dict | None, optional
            Extra arguments to pass to boto3 download_file.
        transfer_config : TransferConfig | None, optional
            Transfer configuration for the download.
        create_parents : bool, optional
            Whether to create parent directories. Default is True.
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

    Similar to :class:`S3_Bucket_Key` but uses folder + file_name instead of a single key.

    Attributes
    ----------
    file_name : str
        The file name within the folder.
    treat_as_folder : bool
        Always False for this class.
    """
    file_name: str  #: The file name within the folder
    treat_as_folder: bool = False  #: Always treat as a file

    # Note the order of decorators matters!
    # noinspection PyNestedDecorators
    @field_validator('file_name')
    @classmethod
    def validate_file_name(cls, v):
        """
        Validate and convert the file_name to a string.

        Parameters
        ----------
        v : Any
            File name value to validate.

        Returns
        -------
        str
            Validated file name string.

        Raises
        ------
        ConfigError
            If the file name is an empty string.
        """
        # Handle pathlib values
        if not isinstance(v, str):
            v = str(v)
        if len(v) == 0:
            raise ConfigError("Zero length string not a valid file_name")
        return v

    def model_post_init(self, __context: Any) -> None:
        """
        Initialize the key attribute after model creation.

        Parameters
        ----------
        __context : Any
            Pydantic context (unused).
        """
        self.key = self._get_key()

    def __repr__(self):
        """
        Return unambiguous string representation for debugging.

        Returns
        -------
        str
            String showing bucket_name, folder, and file_name attributes.
        """
        return f"S3_Bucket_Folder_File({self.bucket_name=}, {self.folder=}, {self.file_name=})"

    def _get_key(self, extra_key: Optional[Union[str, PurePosixPath]] = None) -> str:
        """
        Construct the full S3 key from folder and file_name.

        Parameters
        ----------
        extra_key : str | PurePosixPath | None, optional
            Additional key component to append.

        Returns
        -------
        str
            The complete S3 key string.
        """
        if self._non_blank_key(extra_key):
            return str(PurePosixPath(self.folder) / self.file_name / extra_key)
        else:
            return str(PurePosixPath(self.folder) / self.file_name)

    def upload_specified_file(
        self,
        local_filename: Union[str, Path],
        extra_args: Optional[dict] = None,
        transfer_config: Optional[TransferConfig] = None,
    ):
        """
        Upload a local file to this S3 folder/file location.

        .. deprecated::
            Use :meth:`upload_file` instead.

        Parameters
        ----------
        local_filename : str | Path
            Path to the local file to upload.
        extra_args : dict | None, optional
            Extra arguments to pass to boto3 upload_file.
        transfer_config : TransferConfig | None, optional
            Transfer configuration for the upload.
        """
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
        local_filename: Union[str, Path],
        extra_args: Optional[dict] = None,
        transfer_config: Optional[TransferConfig] = None,
    ):
        """
        Download this S3 object to a local file.

        .. deprecated::
            Use :meth:`download_file` instead.

        Parameters
        ----------
        local_filename : str | Path
            Path where the downloaded file will be saved.
        extra_args : dict | None, optional
            Extra arguments to pass to boto3 download_file.
        transfer_config : TransferConfig | None, optional
            Transfer configuration for the download.
        """
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

    last_modified = S3_Bucket_Key.last_modified  #: Property inherited from :class:`S3_Bucket_Key`
    size = S3_Bucket_Key.size  #: Property inherited from :class:`S3_Bucket_Key`
    iter_versions = S3_Bucket_Key.iter_versions  #: Method inherited from :class:`S3_Bucket_Key`
