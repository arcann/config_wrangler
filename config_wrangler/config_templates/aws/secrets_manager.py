from typing import TYPE_CHECKING

from pydantic import PrivateAttr

from config_wrangler.config_templates.aws.aws_session import AWS_Session

if TYPE_CHECKING:
    # https://youtype.github.io/boto3_stubs_docs/mypy_boto3_ssm/
    from mypy_boto3_secretsmanager.client import SecretsManagerClient
    from mypy_boto3_secretsmanager.type_defs import GetSecretValueResponseTypeDef


class SecretsManager(AWS_Session):
    _service: str = PrivateAttr(default='secretsmanager')
    # Region is not optional for SecretsManager
    region_name: str

    @property
    def client(self) -> 'SecretsManagerClient':
        return super().client

    def get_secret_value_response(self, secret_id: str) -> 'GetSecretValueResponseTypeDef':
        return self.client.get_secret_value(SecretId=secret_id)

    def get_secret_value_by_id(self, secret_id: str) -> str:
        response = self.get_secret_value_response(secret_id=secret_id)
        try:
            return response['SecretString']
        except KeyError:
            raise ValueError(f"{secret_id} did not have SecretString. Maybe it's binary?")

    def get_secret_value_bytes_by_id(self, secret_id: str) -> bytes:
        response = self.get_secret_value_response(secret_id=secret_id)
        try:
            return response['SecretBinary']
        except KeyError:
            raise ValueError(f"{secret_id} did not have SecretBinary. Maybe it's string?")


class SecretValue(SecretsManager):
    secret_id: str

    def get_secret_value(self) -> str:
        return self.get_secret_value_by_id(secret_id=self.secret_id)

    def get_secret_value_bytes(self) -> bytes:
        return self.get_secret_value_bytes_by_id(secret_id=self.secret_id)
