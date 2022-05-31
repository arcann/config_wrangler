import typing
from datetime import date, time, datetime

from pydantic import DirectoryPath, Field, AnyHttpUrl

from config_wrangler.config_from_ini_env import ConfigFromIniEnv
from config_wrangler.config_templates.config_hierarchy import ConfigHierarchy
from config_wrangler.config_templates.s3_bucket import S3_Bucket
from config_wrangler.config_templates.sqlalchemy_database import SQLAlchemyDatabase
from config_wrangler.config_types.path_types import AutoCreateDirectoryPath


class S3_Bucket_KeyPrefixes(S3_Bucket):
    key_prefixes: typing.List[str]


class Environment(ConfigHierarchy):
    name: str = Field(..., env='env_name')
    temp_data_dir: AutoCreateDirectoryPath
    source_data_dir: DirectoryPath


class TestSection(ConfigHierarchy):
    my_int: int
    my_float: float
    my_bool: bool
    my_str: str
    my_bytes: bytes
    my_list_auto_c: list
    my_list_auto_nl: list
    my_list_auto_pipe: list
    my_list_python: list
    my_list_json: list
    my_list_c: list = Field(delimiter=',')
    my_list_nl: list = Field(delimiter='\n')
    my_list_int_c: typing.List[int] = Field(delimiter=',')
    my_tuple_c: tuple = Field(delimiter=',')
    my_tuple_nl: tuple = Field(delimiter='\n')
    my_tuple_int_c: typing.Tuple[int, int, int] = Field(delimiter=',')
    my_dict: dict
    my_dict_str_int: typing.Dict[str, int]
    my_set: set
    my_set_int: typing.Set[int]
    my_frozenset: frozenset
    my_date: date
    my_time: time
    my_datetime: datetime
    my_url: AnyHttpUrl
    double_interpolate: str
    my_environment: Environment


class ETLConfig(ConfigFromIniEnv):

    class Config:
        validate_all = True
        validate_assignment = True
        allow_mutation = True

    target_database: SQLAlchemyDatabase

    s3_source: S3_Bucket_KeyPrefixes

    test_section: TestSection


def main():
    config = ETLConfig(file_name='simple_example.ini')

    print(f"Temp data dir = {config.test_section.my_environment.temp_data_dir}")

    print(f"Source data dir = {config.test_section.my_environment.source_data_dir}")

    print(f"my_int = {config.test_section.my_int}")

    print(f"my_float = {config.test_section.my_float}")

    print(f"my_str = {config.test_section.my_str}")

    print(f"my_list_auto_c = {config.test_section.my_list_auto_c}")

    print(f"my_list_auto_nl = {config.test_section.my_list_auto_nl}")

    print(f"my_dict = {config.test_section.my_dict}")

    print(f"my_set = {config.test_section.my_set}")

    print(f"my_time = {config.test_section.my_time}")

    print(f"my_datetime = {config.test_section.my_datetime}")

    print(f"my_url = {config.test_section.my_url}")

    print(f"target_database = {config.target_database}")

    # Getting DB engine (requires sqlalchemy optional install
    engine = config.target_database.get_engine()
    print(f"target_database.engine = {engine}")

    print("Getting S3 Data")
    bucket = config.s3_source.get_bucket()
    print(f"S3 bucket definition = {bucket}")
    for prefix in config.s3_source.key_prefixes:
        print(f"  bucket search prefix = {prefix}")


if __name__ == '__main__':
    main()
