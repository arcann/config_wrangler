import logging
from typing import *

from pydantic import DirectoryPath, Field

from config_wrangler.config_from_ini_env import ConfigFromIniEnv
from config_wrangler.config_templates.config_hierarchy import ConfigHierarchy
from config_wrangler.config_templates.logging_config import LoggingConfig
from config_wrangler.config_templates.aws.s3_bucket import S3_Bucket
from config_wrangler.config_types.path_types import AutoCreateDirectoryPath


# noinspection PyPep8Naming
class S3_Bucket_KeyPrefixes(S3_Bucket):
    key_prefixes: List[str]


class Environment(ConfigHierarchy):
    name: str = Field(..., env='env_name')
    temp_data_dir: AutoCreateDirectoryPath
    source_data_dir: DirectoryPath


class TestSection(ConfigHierarchy):
    iterations: int = 5


class LoggingExampleConfig(ConfigFromIniEnv):

    class Config:
        validate_default = True
        validate_assignment = True

    test_section: TestSection

    logging: LoggingConfig


def main():
    config = LoggingExampleConfig(file_name='logging_example.ini')

    config.logging.setup_logging()

    log = logging.getLogger('')
    log.info('Got logger')

    with config.logging.log_file_manager(log_file_prefix='test_logging_example'):
        # Debug entries will only go into the file
        # see logging_example.ini
        # [logging]
        # console_log_level = INFO
        # file_log_level = DEBUG
        for i in range(config.test_section.iterations):
            log.debug(f"Debug Iteration {i}")

        for i in range(config.test_section.iterations):
            log.info(f"Info Itteration {i}")


if __name__ == '__main__':
    main()
