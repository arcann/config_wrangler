from typing import TYPE_CHECKING, Union


from pydantic import PrivateAttr
from config_wrangler.config_templates.aws.aws_session import AWS_Session

try:
    import boto3
    from botocore.exceptions import ClientError
except ImportError:
    raise ImportError("Lambda requires boto3 to be installed")

if TYPE_CHECKING:
    # https://youtype.github.io/boto3_stubs_docs/mypy_boto3_s3/client/
    from mypy_boto3_lambda import LambdaClient
    from mypy_boto3_lambda.type_defs import InvocationResponseTypeDef, InvokeWithResponseStreamResponseTypeDef


class Lambda(AWS_Session):
    _service: str = PrivateAttr(default='lambda')

    @property
    def client(self) -> 'LambdaClient':
        return super().client

    def invoke_function(
            self,
            function_name: str,
            invocation_type: str = 'RequestResponse',
            qualifier: str = ...,
            payload: Union[str, bytes] = ...,
            client_context: str = ...,
            include_log_tail: bool = False,
    ) -> 'InvocationResponseTypeDef':
        if isinstance(payload, str):
            payload = payload.encode('utf-8')

        kwargs = {}
        if qualifier is not ...:
            kwargs['Qualifier'] = qualifier
        if payload is not ...:
            kwargs['Payload'] = payload
        if include_log_tail:
            kwargs['LogType'] = 'Tail'
        if client_context is not ...:
            kwargs['ClientContext'] = client_context

        # noinspection PyTypeChecker
        return self.client.invoke(
            FunctionName=function_name,
            InvocationType=invocation_type,
            **kwargs
        )

    def invoke_with_response_stream(
            self,
            function_name: str,
            invocation_type: str = 'RequestResponse',
            qualifier: str = ...,
            payload: Union[str, bytes] = ...,
            client_context: str = ...,
            include_log_tail: bool = False,
            ) -> 'InvokeWithResponseStreamResponseTypeDef':
        if isinstance(payload, str):
            payload = payload.encode('utf-8')

        kwargs = {}
        if qualifier is not ...:
            kwargs['Qualifier'] = qualifier
        if payload is not ...:
            kwargs['Payload'] = payload
        if include_log_tail:
            kwargs['LogType'] = 'Tail'
        if client_context is not ...:
            kwargs['ClientContext'] = client_context

        # noinspection PyTypeChecker
        return self.client.invoke_with_response_stream(
            FunctionName=function_name,
            InvocationType=invocation_type,
            **kwargs
        )
