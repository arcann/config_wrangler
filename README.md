# Config Wrangler

[![pypi](https://img.shields.io/pypi/v/config-wrangler.svg)](https://pypi.org/project/config-wrangler/)
[![license](https://img.shields.io/github/license/arcann/config_wrangler.svg)](https://github.com/arcann/config_wrangler/blob/master/LICENSE)

pydantic based configuration wrangler. Handles reading multiple ini or toml files with inheritance rules and variable expansions.



## Installation

Install using `pip install -U config-wrangler` or `conda install config-wrangler -c conda-forge`.

## A Simple Example

config.ini
```ini
[S3_Source]
bucket_name=my.exmple-bucket
key_prefixes=processed/
user_id=AK123456789ABC
# Not a secure way to store the password, but OK for local prototype or examples.
# See KEYRING or KEEPASS for better options
password_source=CONFIG_FILE
raw_password=My secret password

[target_database]
dialect=sqlite
database_name=${test_section:my_environment:source_data_dir}/example_db

[test_section]
my_int=123
my_float=123.45
my_bool=Yes
my_str=ABC☕
my_bytes=ABCⓁⓄⓋ☕
my_list_auto_c=a,b,c
my_list_auto_nl=
    a
    b
    c
my_list_auto_pipe=a|b|c
my_list_c=a,b,c
my_list_python=['x','y','z']
my_list_json=["J","S","O","N"]
my_list_nl=
    a
    b
    c
my_list_int_c=1,2,3
my_tuple_c=a,b,c
my_tuple_nl=
    a
    b
    c
my_tuple_int_c=1,2,3
my_dict={1: "One", 2: "Two"}
my_dict_str_int={"one": 1, "two": 2}
my_set={'A','B','C'}
my_set_int=1,2,3
my_frozenset=A,B,C
my_date=2021-05-31
my_time=11:55:23
my_datetime=2021-05-31 11:23:53
my_url=https://localhost:6553/

[test_section.my_environment]
name=dev
# For example to run we'll make both paths relative to current
temp_data_dir=.\temp_data\${test_section:my_environment:name}
source_data_dir=.
```

python code

```py
import typing
from datetime import date, time, datetime

from pydantic import BaseModel, DirectoryPath, Field, AnyHttpUrl

from config_wrangler.config_data_loaders.base_config_data_loader import BaseConfigDataLoader
from config_wrangler.config_from_ini_env import ConfigFromIniEnv
from config_wrangler.config_from_loaders import ConfigFromLoaders
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


class TestSection(BaseModel):
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
    my_environment: Environment


class ETLConfig(ConfigFromIniEnv):
    class Config:
        validate_all = True
        validate_assignment = True
        allow_mutation = True

    target_database: SQLAlchemyDatabase

    s3_source: S3_Bucket_KeyPrefixes

    test_section: TestSection


class ETLConfigAnyLoaders(ETLConfig):
    def __init__(
            self,
            _config_data_loaders: typing.List[BaseConfigDataLoader],
            **kwargs: typing.Dict[str, typing.Any]
    ) -> None:
        # Skip super and call the next higher class
        ConfigFromLoaders.__init__(
            self,
            _config_data_loaders=_config_data_loaders,
            **kwargs
        )


def main():
    config = ETLConfig(file_name='simple_example.ini')

    print(f"Temp data dir = {config.test_section.my_environment.temp_data_dir}")
    # > Temp data dir = temp_data\dev

    print(f"Source data dir = {config.test_section.my_environment.source_data_dir}")
    # > Source data dir = .

    print(f"my_int = {config.test_section.my_int}")
    # > my_int = 123

    print(f"my_float = {config.test_section.my_float}")
    # > my_float = 123.45

    print(f"my_str = {config.test_section.my_str}")
    # > my_str = ABC☕

    print(f"my_list_auto_c = {config.test_section.my_list_auto_c}")
    # > my_list_auto_c = ['a', 'b', 'c']

    print(f"my_list_auto_nl = {config.test_section.my_list_auto_nl}")
    # > my_list_auto_c = ['a', 'b', 'c']

    print(f"my_dict = {config.test_section.my_dict}")
    # > my_dict = {1: 'One', 2: 'Two'}

    print(f"my_set = {config.test_section.my_set}")
    # > my_set = {'C', 'A', 'B'}

    print(f"my_time = {config.test_section.my_time}")
    # > my_time = 11:55:23

    print(f"my_datetime = {config.test_section.my_datetime}")
    # > my_datetime = 2021-05-31 11:23:53

    print(f"my_url = {config.test_section.my_url}")
    # > my_url = https://localhost:6553/

    # Getting DB engine (requires sqlalchemy optional install
    engine = config.target_database.get_engine()
    print(f"target_database.engine = {engine}")
    # > target_database.engine = Engine(sqlite:///.example_db)

    print("Getting S3 Data")
    bucket = config.s3_source.get_bucket()
    print(f"S3 bucket definition = {bucket}")
    for prefix in config.s3_source.key_prefixes:
        print(f"  bucket search prefix = {prefix}")
    # > Getting S3 Data
    # > credentials.py:56: UserWarning: Passwords stored directly in config or worse in code are not safe. Please make sure to fix this before deploying.
    # > S3 bucket definitition = s3.Bucket(name='my.exmple-bucket')
    # > bucket search prefix = processed/


if __name__ == '__main__':
    main()

```
