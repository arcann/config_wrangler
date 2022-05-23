import logging
import sys
import typing
from contextlib import contextmanager
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

from CaseInsensitiveDict import CaseInsensitiveDict
from pydantic import ByteSize

from config_wrangler.config_templates.config_hierarchy import ConfigHierarchy
from config_wrangler.config_types.path_types import AutoCreateDirectoryPath
from config_wrangler.utils import TZFormatter
from config_wrangler.config_types.enum import StrEnum, auto_str


class LogLevel(StrEnum):
    CRITICAL = auto_str()
    FATAL = auto_str()
    ERROR = auto_str()
    WARNING = auto_str()
    INFO = auto_str()
    DEBUG = auto_str()
    NOTSET = auto_str()


class LoggingConfig(ConfigHierarchy):
    console_log_level: LogLevel = LogLevel.INFO
    console_entry_format: str = '%(asctime)s - %(levelname)-8s - %(name)s: %(message)s'
    log_folder: AutoCreateDirectoryPath
    log_file_name: str = None
    add_date_to_log_file_name: bool = True
    log_file_name_date_time_format: str = '_%Y_%m_%d_at_%H_%M_%S'
    file_log_level: LogLevel = LogLevel.DEBUG
    log_file_entry_format: str = '%(asctime)s - %(levelname)-8s - %(name)s: %(message)s'
    log_file_max_size: ByteSize = ByteSize.validate('10 MB').to('b')
    log_files_to_keep: int = 10
    logging_date_format: str = '%Y-%m-%d %H:%M:%S%z'
    trace_logging_setup: bool = False
    log_levels: typing.Dict[str, LogLevel]

    @staticmethod
    def get_dated_log_file_name(
            log_file_prefix: str,
            date_time_format: str,
            log_file_suffix: str = '.log',
    ):
        """
        Generates a log file name with a given prefix, suffix and date time format.

        Parameters
        ----------
        log_file_prefix: str
            The part of the log file name before the date
        log_file_suffix: str
            The part of the log file name after the date
        date_time_format: str
            Optional. The date time format to use. Defaults to '_%Y_%m_%d_at_%H_%M_%S'
        """
        return f"{log_file_prefix}{datetime.now().strftime(date_time_format)}{log_file_suffix}"

    def add_log_file_handler(
            self,
            log_file_prefix: str = None,
            add_date_to_log_file_name: bool = None,
            log_file_suffix: str = '.log',
    ) -> logging.Handler:
        log = logging.getLogger(__name__)
        root_logger = logging.getLogger()
        if add_date_to_log_file_name is None:
            add_date_to_log_file_name = self.add_date_to_log_file_name
        if log_file_prefix is None:
            if self.log_file_name is not None:
                log_file_name = self.log_file_name
            else:
                log_file_name = None
        else:
            if add_date_to_log_file_name:
                log_file_name = LoggingConfig.get_dated_log_file_name(
                    log_file_prefix=log_file_prefix,
                    date_time_format=self.log_file_name_date_time_format,
                    log_file_suffix=log_file_suffix,
                )
            else:
                log_file_name = f"{log_file_prefix}.{log_file_suffix}"

        file_handler = None
        if log_file_name is not None:
            if self.log_folder is not None and not Path(log_file_name).is_absolute():
                log_file_path = Path(self.log_folder, log_file_name)
            else:
                log_file_path = Path(log_file_name)

            if self.trace_logging_setup:
                log.info('Logging path = {}'.format(log_file_path))

            # Setup file logging

            # Make sure the directory exists
            dir_name = log_file_path.parent
            if dir_name.is_absolute():
                dir_name.mkdir(parents=True, exist_ok=True)

            file_handler = RotatingFileHandler(filename=log_file_path,
                                               maxBytes=self.log_file_max_size,
                                               backupCount=self.log_files_to_keep,
                                               encoding='utf8',
                                               )
            log_file_entry_formatter = TZFormatter(self.log_file_entry_format, self.logging_date_format)
            file_handler.setFormatter(log_file_entry_formatter)
            file_handler.setLevel(self.file_log_level)
            root_logger.addHandler(file_handler)
            log.info('File log level = {}'.format(self.file_log_level))
        else:
            if self.trace_logging_setup:
                log.info('No log filename defined. File logging skipped.')
        return file_handler

    def remove_log_handler(self, handler: logging.Handler):
        log = logging.getLogger(__name__)
        if handler is not None:
            if self.trace_logging_setup:
                log.info(f"Closing log handler {handler}")
            root_logger = logging.getLogger()
            root_logger.removeHandler(handler)
            handler.close()
        else:
            if self.trace_logging_setup:
                log.info('No handler provided to remove_log_handler')

    @contextmanager
    def log_file_manager(
            self,
            log_file_prefix: str = None,
            add_date_to_log_file_name: bool = False,
            log_file_suffix: str = '.log',
    ):
        log_file_handler = self.add_log_file_handler(
            log_file_prefix=log_file_prefix,
            add_date_to_log_file_name=add_date_to_log_file_name,
            log_file_suffix=log_file_suffix,
        )
        try:
            yield log_file_handler
        finally:
            # Code to release resource, e.g.:
            self.remove_log_handler(log_file_handler)

    def setup_log_levels(self):
        configured_loggers = dict()
        root_logger = logging.getLogger()

        # Monkey-patch getLogger's dict to be case-insensitive        
        logger_dict = CaseInsensitiveDict(logging.Logger.manager.loggerDict)  # @UndefinedVariable
        logging.Logger.manager.loggerDict = logger_dict

        for logger_class, desired_level_name in self.log_levels.items():
            if logger_class.lower() == 'root':
                logger = root_logger
            else:
                logger = logging.getLogger(logger_class)
            configured_loggers[logger_class] = logger
            logger.propagate = True
            if desired_level_name is None:
                desired_level_name = 'INFO'
            else:
                desired_level_name = desired_level_name.upper()
            if self.trace_logging_setup:
                # Note: We can't use logging here yet
                print(f'Setting logger {logger.name} to {desired_level_name}')
            logger.setLevel(desired_level_name)

        # Will not include root logger
        for logger_class in sorted(logging.Logger.manager.loggerDict):
            logger = logging.getLogger(logger_class)
            if self.trace_logging_setup:
                print(f'Logger {logger_class} handlers {logger.handlers}')
            if logger_class not in configured_loggers:
                if self.trace_logging_setup:
                    # Note: We can't use logging here yet
                    print(
                        f"Checking existing logger {logger_class} "
                        f"level {logging.getLevelName(logger.getEffectiveLevel())}"
                    )
                for compare_logger in sorted(configured_loggers):
                    if logger_class.startswith(compare_logger):
                        parent_logger = configured_loggers[compare_logger]
                        level = parent_logger.getEffectiveLevel()
                        logger.setLevel(level)
                        if self.trace_logging_setup:
                            # Note: We can't use logging here yet
                            print(
                                f"Existing logger {logger_class} re-setup with {parent_logger.name} "
                                f"settings {logging.getLevelName(level)}"
                            )
                        logger.propagate = True

        if self.trace_logging_setup:
            # Note: We can't use logging here yet
            print(f"Root logging level is {logging.getLevelName(root_logger.getEffectiveLevel())}")
            print(f"Root logging handlers are {root_logger.handlers}")

    def setup_logging(
            self,
            log_file_prefix: str = None,
            add_date_to_log_file_name: bool = None,
            log_file_suffix: str = '.log',
            console_output=None,
            use_log_file_setting=True,
    ):
        """
        Setup logging based on configuration.
        """

        root_logger = logging.getLogger()

        if not hasattr(root_logger, 'config_wrangler_setup_done'):
            # Store info that we have already setup logging in the root logger.
            # This could be stored in the config, it would be too easy for methods to open
            # their own configs and thus will not know the logging had already been setup.
            root_logger.config_wrangler_setup_done = True

            # Close out any existing handlers
            for handler in root_logger.handlers:
                handler.flush()
                handler.close()

            # Reset the handlers
            root_logger.handlers.clear()

            if self.trace_logging_setup:
                # Note: We can't use logging here yet
                print('logging.trace_setup is True}')
                print(f'Starting root logger handlers {root_logger.handlers}')

            # Modify the root logger level to at least INFO for now. setup_log_levels could change it
            root_logger.setLevel(logging.INFO)

            if console_output is None:
                error_output = sys.stderr
                regular_output = sys.stdout
            else:
                error_output = console_output
                regular_output = console_output

            console_error_log = logging.StreamHandler(error_output)
            console_error_log.setLevel(logging.ERROR)
            root_logger.addHandler(console_error_log)

            console_log = logging.StreamHandler(regular_output)
            console_log.setLevel(self.console_log_level)

            # define a filter for non-error messages
            def non_error(record):
                return record.levelno != logging.ERROR

            # Errors go to console_error_log above, so we don't want them here as well
            console_log.addFilter(non_error)

            root_logger.addHandler(console_log)

            console_entry_format = self.console_entry_format
            if console_entry_format:
                console_entry_formater = TZFormatter(console_entry_format, self.logging_date_format)
                console_log.setFormatter(console_entry_formater)
                console_error_log.setFormatter(console_entry_formater)

            self.setup_log_levels()

            # Switch to this modules logger
            log = logging.getLogger(__name__)

            logging.captureWarnings(True)

            log_level_name = logging.getLevelName(log.getEffectiveLevel())
            if self.trace_logging_setup:
                log.info('This modules logging level is {}'.format(log_level_name))

            if use_log_file_setting or log_file_prefix is not None:
                return self.add_log_file_handler(
                    log_file_prefix=log_file_prefix,
                    add_date_to_log_file_name=add_date_to_log_file_name,
                    log_file_suffix=log_file_suffix,
                )
            else:
                if self.trace_logging_setup:
                    log.info('use_log_file_setting = False. setup_log_file not called.')
                return None
