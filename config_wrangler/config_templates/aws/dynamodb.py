import logging
import timeit
import warnings
from typing import *

from pydantic import PrivateAttr

from config_wrangler.config_templates.aws.aws_session import AWS_Session

if TYPE_CHECKING:
    try:
        import botostubs
    except ImportError:
        botostubs = None


class DynamoDB(AWS_Session):
    _service: str = PrivateAttr(default='dynamodb')
    scan_progress_seconds: int = 10

    def get_dynamo_table(
            self,
            dynamo_table_name,
            region_name: str = None
    ) -> 'botostubs.DynamoDB.DynamodbResource.Table':
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
            dynamo_table: 'botostubs.DynamoDB.DynamodbResource.Table',
            scan_args_list: Iterator[dict],
    ) -> Iterator[dict]:
        log = logging.getLogger('DynamoDB')
        data = []

        start_time = timeit.default_timer()
        page = 0

        for scan_args in scan_args_list:
            page += 1
            tbl_data = dynamo_table.query(**scan_args)
            data.extend(tbl_data['Items'])

            while 'LastEvaluatedKey' in tbl_data:
                page += 1
                if (timeit.default_timer() - start_time) > self.scan_progress_seconds:
                    log.info(f"Processing query page {page:,}")
                    start_time = timeit.default_timer()
                tbl_data = dynamo_table.query(ExclusiveStartKey=tbl_data['LastEvaluatedKey'], **scan_args)
                data.extend(tbl_data['Items'])

        return data

    def query_dynamo_table_by_name(
            self,
            dynamo_table_name: str,
            scan_args_list: Iterator[dict],
            region_name: str = None,  # Deprecated
    ) -> Iterator[dict]:
        dynamo_table = self.get_dynamo_table(dynamo_table_name, region_name=region_name)
        return self.query_dynamo_table(dynamo_table, scan_args_list)

    def scan_dynamo_table(
            self,
            dynamo_table: 'botostubs.DynamoDB.DynamodbResource.Table',
    ):
        log = logging.getLogger('DynamoDB')
        data = []
        tbl_data = dynamo_table.scan()
        data.extend(tbl_data['Items'])

        start_time = timeit.default_timer()
        page = 0

        while 'LastEvaluatedKey' in tbl_data:
            page += 1
            if (timeit.default_timer() - start_time) > self.scan_progress_seconds:
                log.info(f"Processing scan page {page:,}")
                start_time = timeit.default_timer()
            tbl_data = dynamo_table.scan(ExclusiveStartKey=tbl_data['LastEvaluatedKey'])
            data.extend(tbl_data['Items'])

        return data

    def scan_dynamo_table_by_name(
            self,
            dynamo_table_name: str,
            region_name: str = None  # Deprecated
    ):
        dynamo_table = self.get_dynamo_table(dynamo_table_name, region_name=region_name)
        return self.scan_dynamo_table(dynamo_table)


class DynamoDB_Table(DynamoDB):
    table_name: str

    def get_dynamo_table(self, **kwargs) -> 'botostubs.DynamoDB.DynamodbResource.Table':
        parent_table_arg = 'dynamo_table_name'
        if parent_table_arg in kwargs and kwargs[parent_table_arg] is not None:
            return super().get_dynamo_table(dynamo_table_name=kwargs[parent_table_arg])
        else:
            return super().get_dynamo_table(dynamo_table_name=self.table_name)

    def query_dynamo_table(
            self,
            scan_args_list: Iterator[dict],
            **kwargs
    ) -> Iterator[dict]:
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

    def put_item(self, Item: 'botostubs.DynamoDB.PutItemInputAttributeMap') -> dict:
        return self.get_dynamo_table().put_item()
