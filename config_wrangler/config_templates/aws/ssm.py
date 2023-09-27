from typing import TYPE_CHECKING, List

from pydantic import PrivateAttr

from config_wrangler.config_templates.aws.aws_session import AWS_Session

if TYPE_CHECKING:
    # https://youtype.github.io/boto3_stubs_docs/mypy_boto3_ssm/
    from mypy_boto3_ssm.client import SSMClient
    from mypy_boto3_ssm.type_defs import (
        GetParameterResultTypeDef,
        GetParametersResultTypeDef,
        GetParametersByPathResultTypeDef,
    )


class SSM(AWS_Session):
    _service: str = PrivateAttr(default='ssm')
    # Region is not optional for SSM
    region_name: str

    @property
    def client(self) -> 'SSMClient':
        return super().client

    def get_parameters_response(
            self,
            names: List[str],
            with_decryption: bool = True,
    ) -> 'GetParametersResultTypeDef':
        return self.client.get_parameters(
            Names=names,
            WithDecryption=with_decryption,
        )

    def get_parameters(
            self,
            names: List[str],
            with_decryption: bool = True,
    ) -> dict:
        response = self.get_parameters_response(names=names, with_decryption=with_decryption)
        return {entry['Name']: entry['Value'] for entry in response['Parameters']}

    def get_parameters_by_path_response(
            self,
            path: str,
            recursive: bool = True,
            with_decryption: bool = True,
    ) -> 'GetParametersByPathResultTypeDef':
        return self.client.get_parameters_by_path(
            Path=path,
            Recursive=recursive,
            WithDecryption=with_decryption,
        )

    def get_parameters_by_path(
            self,
            path: str,
            recursive: bool = True,
            with_decryption: bool = True,
    ) -> dict:
        response = self.get_parameters_by_path_response(
            path=path,
            recursive=recursive,
            with_decryption=with_decryption,
        )
        return {
            entry['Name']: entry['Value']
            for entry in response['Parameters']
        }

    def get_parameter_response(
            self,
            name: str,
            with_decryption: bool = True,
    ) -> 'GetParameterResultTypeDef':
        return self.client.get_parameter(
            Name=name,
            WithDecryption=with_decryption,
        )

    def get_parameter_value(
            self,
            name: str,
            with_decryption: bool = True,
    ) -> str:
        ssm_response = self.get_parameter_response(name, with_decryption)
        return ssm_response['Parameter']['Value']


# noinspection PyPep8Naming
class SSM_Parameter(SSM):
    parameter_name: str

    def get_value(self):
        return self.get_parameter_value(self.parameter_name)
