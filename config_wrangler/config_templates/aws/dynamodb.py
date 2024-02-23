import logging
import timeit
import warnings
from typing import *

from pydantic import PrivateAttr

from config_wrangler.config_templates.aws.aws_session import AWS_Session

if TYPE_CHECKING:
    # https://youtype.github.io/boto3_stubs_docs/mypy_boto3_dynamodb/
    from mypy_boto3_dynamodb.service_resource import DynamoDBServiceResource
    from mypy_boto3_dynamodb.client import DynamoDBClient
    from mypy_boto3_dynamodb.service_resource import Table
    from mypy_boto3_dynamodb.type_defs import PutItemOutputTableTypeDef
    import pynamodb.models


class DynamoDB(AWS_Session):
    _service: str = PrivateAttr(default='dynamodb')
    scan_progress_seconds: int = 10

    @property
    def resource(self) -> 'DynamoDBServiceResource':
        return super().resource

    @property
    def client(self) -> 'DynamoDBClient':
        return super().client

    def get_dynamo_table(
            self,
            dynamo_table_name,
            region_name: str = None
    ) -> 'Table':
        if region_name is not None:
            warnings.warn(
                "DynamoDB.get_dynamo_table argument region_name is deprecated. "
                "Use DynamoDB.region_name property instead."
            )
            if self.region_name != region_name:
                warnings.warn(
                    f"DynamoDB.get_dynamo_table argument region_name value '{region_name}' conflicts with "
                    f"DynamoDB.region_name value '{self.region_name}! "
                    "Deprecated argument value was ignored."
                )
        dynamodb = self.resource

        return dynamodb.Table(dynamo_table_name)

    def query_dynamo_table(
            self,
            dynamo_table: 'Table',
            scan_args_list: Iterator[dict],
    ) -> Iterable[dict]:
        log = logging.getLogger('DynamoDB')
        start_time = timeit.default_timer()
        page = 1
        for scan_args in scan_args_list:
            page += 1
            tbl_data = dynamo_table.query(**scan_args)
            for item in tbl_data['Items']:
                yield item

            while 'LastEvaluatedKey' in tbl_data:
                page += 1
                if (timeit.default_timer() - start_time) > self.scan_progress_seconds:
                    log.info(f"Processing query page {page:,}")
                    start_time = timeit.default_timer()
                tbl_data = dynamo_table.query(ExclusiveStartKey=tbl_data['LastEvaluatedKey'], **scan_args)
                for item in tbl_data['Items']:
                    yield item

    def query_dynamo_table_by_name(
            self,
            dynamo_table_name: str,
            scan_args_list: Iterator[dict],
            region_name: str = None,  # Deprecated
    ) -> Iterable[dict]:
        dynamo_table = self.get_dynamo_table(dynamo_table_name, region_name=region_name)
        yield from self.query_dynamo_table(dynamo_table, scan_args_list)

    def scan_dynamo_table(
        self,
        dynamo_table: 'Table',
    ) -> Iterator[dict]:
        log = logging.getLogger('DynamoDB')
        start_time = timeit.default_timer()
        tbl_data = dynamo_table.scan()
        for item in tbl_data['Items']:
            yield item

        page = 1
        while 'LastEvaluatedKey' in tbl_data:
            page += 1
            if (timeit.default_timer() - start_time) > self.scan_progress_seconds:
                log.info(f"Processing scan page {page:,}")
                start_time = timeit.default_timer()
            tbl_data = dynamo_table.scan(ExclusiveStartKey=tbl_data['LastEvaluatedKey'])
            for item in tbl_data['Items']:
                yield item

    def scan_dynamo_table_by_name(
            self,
            dynamo_table_name: str,
            region_name: str = None  # Deprecated
    ) -> Iterable[dict]:
        dynamo_table = self.get_dynamo_table(dynamo_table_name, region_name=region_name)
        yield from self.scan_dynamo_table(dynamo_table)


class DynamoDBTable(DynamoDB):
    table_name: str

    def get_dynamo_table(self, **kwargs) -> 'Table':
        parent_table_arg = 'dynamo_table_name'
        if parent_table_arg in kwargs and kwargs[parent_table_arg] is not None:
            return super().get_dynamo_table(dynamo_table_name=kwargs[parent_table_arg])
        else:
            return super().get_dynamo_table(dynamo_table_name=self.table_name)

    def query_dynamo_table(
            self,
            scan_args_list: Iterator[dict],
            **kwargs
    ) -> Iterable[dict]:
        parent_table_arg = 'dynamo_table_name'
        if parent_table_arg in kwargs and kwargs[parent_table_arg] is not None:
            return super().query_dynamo_table(
                dynamo_table=kwargs[parent_table_arg],
                scan_args_list=scan_args_list,
            )
        else:
            return super().query_dynamo_table(
                dynamo_table=self.get_dynamo_table(),
                scan_args_list=scan_args_list,
            )

    def scan_dynamo_table(
        self,
        **kwargs
    ):
        parent_table_arg = 'dynamo_table'
        if parent_table_arg in kwargs and kwargs[parent_table_arg] is not None:
            return super().scan_dynamo_table(
                dynamo_table=kwargs[parent_table_arg],
            )
        else:
            return super().scan_dynamo_table(
                dynamo_table=self.get_dynamo_table(),
            )

    def put_item(self, item: Mapping[str, Any]) -> 'PutItemOutputTableTypeDef':
        return self.get_dynamo_table().put_item(Item=item)

    def get_connected_pynamodb(
        self,
        model: 'pynamodb.models.Model',
        connect_table_name: Optional[str] = None
    ) -> 'pynamodb.models.Model':
        # Optional library
        from pynamodb.indexes import Index

        if connect_table_name is None:
            connect_table_name = self.table_name or model.Meta.table_name

        # # We need instance specific versions of the Model class
        class _ConnectedClass(model):
            class Meta:
                connected = True
                table_name = connect_table_name

        _ConnectedClass.Meta.region = self.region_name
        _ConnectedClass.Meta.aws_access_key_id = self.user_id
        _ConnectedClass.Meta.aws_secret_access_key = self.get_password()
        # Optional, only for temporary credentials like those received when assuming a role
        credentials = self.session.get_credentials()
        _ConnectedClass.Meta.aws_session_token = credentials.token

        for attribute_name in dir(_ConnectedClass):
            attribute = getattr(_ConnectedClass, attribute_name)
            if isinstance(attribute, Index):

                class InnerIndex(attribute.__class__):
                    class Meta:
                        index_name = attribute.Meta.index_name
                        projection = attribute.Meta.projection

                index_obj = InnerIndex()
                setattr(_ConnectedClass, attribute_name, index_obj)
                index_obj.Meta.model = _ConnectedClass
                index_obj._model = _ConnectedClass
        return _ConnectedClass
