from typing import *

from pydantic import PrivateAttr

try:
    import boto3
except ImportError:
    raise ImportError("AWS_Session requires boto3 to be installed")

if TYPE_CHECKING:
    from config_wrangler.config_templates.aws.s3_bucket import S3_Bucket, S3_Bucket_Key
    from mypy_boto3_sts import STSClient
    from mypy_boto3_sts.type_defs import PolicyDescriptorTypeTypeDef, TagTypeDef, ProvidedContextTypeDef
else:
    # Provide string values so that type hint code compiles
    STSClient = 'STSClient'
    PolicyDescriptorTypeTypeDef = 'PolicyDescriptorTypeTypeDef'
    TagTypeDef = 'TagTypeDef'
    ProvidedContextTypeDef = 'TagTypeDef'

# NOTE: If you are not seeing boto3-stubs code completion in Intellij-based IDEs,
#       please increase the intellisense filesize limit
#       e.g `idea.max.intellisense.filesize=20000` in IDE custom properties
#       (Help > Edit Custom Properties), then restart.

from config_wrangler.config_templates.credentials import Credentials


# AWSSession does not look right, so we added underscores
# noinspection PyPep8Naming
class AWS_Session(Credentials):
    # sso_session: Optional[DynamicallyReferenced] = None
    region_name: Optional[str] = None

    _session: boto3.session.Session = PrivateAttr(default=None)
    _service: str = PrivateAttr(default=None)

    @property
    def session(self) -> boto3.session.Session:
        if self._session is None:
            self._session = boto3.session.Session(
                aws_access_key_id=self.user_id,
                aws_secret_access_key=self.get_password(),
                region_name=self.region_name,
            )
        return self._session

    def set_session(self, session: boto3.session.Session):
        self._session = session

    @property
    def has_session(self) -> bool:
        return self._session is not None

    def _get_client(self, service: str = None):
        if service is None:
            service = self._service
        # noinspection PyTypeChecker
        return self.session.client(service, region_name=self.region_name)

    @property
    def client(self):
        return self._get_client()

    def get_service_client(self, service: str):
        return self._get_client(service=service)

    def sts_assume_role(
            self,
            role_arn: str,
            role_session_name: str,
            policy_arns: Sequence[PolicyDescriptorTypeTypeDef] = ...,
            policy: str = ...,
            duration_seconds: int = ...,
            tags: Sequence[TagTypeDef] = ...,
            transitive_tag_keys: Sequence[str] = ...,
            external_id: str = ...,
            serial_number: str = ...,
            token_code: str = ...,
            source_identity: str = ...,
            provided_contexts: Sequence[ProvidedContextTypeDef] = ...
    ) -> boto3.session.Session:
        sts_client = self.get_service_client('sts')  # type: STSClient
        response = sts_client.assume_role(
            RoleArn=role_arn,
            RoleSessionName=role_session_name,
            PolicyArns=policy_arns,
            Policy=policy,
            DurationSeconds=duration_seconds,
            Tags=tags,
            TransitiveTagKeys=transitive_tag_keys,
            ExternalId=external_id,
            SerialNumber=serial_number,
            TokenCode=token_code,
            SourceIdentity=source_identity,
            ProvidedContexts=provided_contexts,
        )

        session = boto3.session.Session(
            aws_access_key_id=response['Credentials']['AccessKeyId'],
            aws_secret_access_key=response['Credentials']['SecretAccessKey'],
            aws_session_token=response['Credentials']['SessionToken']
        )

        # Should we have this new session become the default?
        self._session = session

        return session

    def _get_resource(self, service: str = None):
        if service is None:
            service = self._service
        # noinspection PyTypeChecker
        return self.session.resource(service, region_name=self.region_name)

    @property
    def resource(self):
        return self._get_resource()

    def get_service_resource(self, service: str):
        return self._get_resource(service=service)

    def get_copy(self, copied_by: str = 'get_copy') -> 'AWS_Session':
        return self._factory(cls=self.__class__)

    def _factory(self, cls, exclude: Set[str] = None, **attributes):
        if exclude is None:
            exclude = set()
        exclude.update(attributes.keys())
        new_object = cls.model_construct(
            **attributes,
            **self._dict_for_init(exclude=exclude)
        )
        self.add_child(str(cls), new_object)
        if self.has_session:
            new_object.set_session(self.session)
        return new_object

    def nav_to_bucket(self, bucket_name) -> 'S3_Bucket':
        from config_wrangler.config_templates.aws.s3_bucket import S3_Bucket
        return self._factory(
            S3_Bucket,
            exclude={'bucket_name', 'folder', 'file_name', 'key'},
            bucket_name=bucket_name,
        )

    @staticmethod
    def split_s3_uri(s3_uri: str) -> Tuple[str, str]:
        parts = s3_uri.split("/", 3)
        # Note 'S3://bucket-name/key-name/file.txt'.split('/', 3)
        # Returns [ 'S3:', '', 'bucket-name', 'key-name/file.txt' ]
        if parts[0].lower() != 's3:' or parts[1] != '':
            raise ValueError(f"S3 URI '{s3_uri}' does not appear to be valid")
        if len(parts) == 3:
            return parts[2], ''
        else:
            return parts[2], parts[3]

    def nav_to_s3_link(self, s3_uri: str) -> 'S3_Bucket_Key':
        bucket, key = self.split_s3_uri(s3_uri)
        return self.nav_to_bucket(bucket) / key

    def get_ssm(self):
        from config_wrangler.config_templates.aws.ssm import SSM
        return self._factory(
            SSM,
        )

    def get_secrets_manager(self):
        from config_wrangler.config_templates.aws.secrets_manager import SecretsManager
        return self._factory(
            SecretsManager,
        )
