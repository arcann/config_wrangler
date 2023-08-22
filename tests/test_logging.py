import logging
import os
import unittest
from datetime import time
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from tempfile import TemporaryDirectory

from config_wrangler.config_from_ini_env import ConfigFromIniEnv
from config_wrangler.config_templates.logging_config import LoggingConfig
from tests.base_tests_mixin import Base_Tests_Mixin


class ConfigWithLogging(ConfigFromIniEnv):
    logging: LoggingConfig


class TestLogging(unittest.TestCase, Base_Tests_Mixin):
    def setUp(self):
        self.logger = logging.getLogger()
        self.orig_handlers = self.logger.handlers
        self.logger.handlers = []
        self.level = self.logger.level

        # Reset the config_wrangler_setup_done attribute if it's been set
        # Normally that prevents two setups, but we need to disable it
        try:
            # noinspection PyUnresolvedReferences
            del self.logger.config_wrangler_setup_done
        except AttributeError:
            pass

        self.saved_cwd = os.getcwd()
        self.temp_dir_handler = TemporaryDirectory(ignore_cleanup_errors=True)
        self.temp_dir = self.temp_dir_handler.name
        os.chdir(self.temp_dir)

    def tearDown(self):
        for handler in self.logger.handlers:
            handler.close()
        self.logger.handlers = self.orig_handlers
        self.logger.level = self.level
        # We need to change back out of the temp dir, so that it can be cleaned up
        os.chdir(self.saved_cwd)
        self.temp_dir_handler.cleanup()

    def test_no_file_handler(self):
        config = ConfigWithLogging(
            file_name='test_logging_no_file.ini',
            start_path=self.get_test_files_path(),
        )
        config.logging.setup_logging()
        self.assertTrue(self.logger.level == logging.INFO)
        my_module_log = logging.getLogger('my_module')
        self.assertTrue(my_module_log.level == logging.DEBUG)

        for handler in self.logger.handlers:
            self.assertFalse(
                isinstance(handler, logging.FileHandler),
                f"root logger included FileHandler based handler {type(handler)} {handler}"
            )

    def test_default_file_handler(self):
        config = ConfigWithLogging(
            file_name='test_logging_default_file.ini',
            start_path=self.get_test_files_path(),
        )
        config.logging.setup_logging()

        self.assertTrue(self.logger.level == logging.INFO)
        my_module_log = logging.getLogger('my_module')
        self.assertTrue(my_module_log.level == logging.DEBUG)

        found_log_handlers = 0
        for handler in self.logger.handlers:
            if isinstance(handler, RotatingFileHandler):
                found_log_handlers += 1
                self.assertIn(self.temp_dir, handler.baseFilename, 'log file name not correct')
                self.assertEqual(config.logging.log_file_max_size, handler.maxBytes, 'maxBytes not set correctly')

        self.assertEqual(1, found_log_handlers, 'Did not find one RotatingFileHandler')

        my_module_log.debug('Test log entry')

        my_module_log.info('done')

    def test_rot_file_handler(self):
        config = ConfigWithLogging(
            file_name='test_logging_rot_file.ini',
            start_path=self.get_test_files_path(),
        )
        config.logging.setup_logging()
        root_logger = logging.getLogger()

        self.assertEqual(1 * 1000 * 1000, config.logging.log_file_max_size, 'log_file_max_size')

        self.assertTrue(
            root_logger.level == logging.INFO,
            f"root logger level not INFO but {root_logger.level}"
        )
        my_module_log = logging.getLogger('my_module')
        self.assertTrue(
            my_module_log.level == logging.DEBUG,
            f"my_module_log logger level not DEBUG but {my_module_log.level}"
        )

        found_log_handlers = 0
        for handler in root_logger.handlers:
            if isinstance(handler, RotatingFileHandler):
                found_log_handlers += 1
                self.assertIn(self.temp_dir, handler.baseFilename, 'log file name not correct')
                self.assertEqual(config.logging.log_file_max_size, handler.maxBytes, 'maxBytes not set correctly')

        self.assertEqual(1, found_log_handlers, 'Did not find one RotatingFileHandler')

        my_module_log.debug('Test log entry')

        my_module_log.info('done')

    def test_timed_rot_file_handler(self):
        config = ConfigWithLogging(
            file_name='test_logging_timed_rot_file.ini',
            start_path=self.get_test_files_path(),
        )
        config.logging.setup_logging()
        root_logger = logging.getLogger()

        self.assertEqual('midnight', config.logging.log_file_timed_rotation_when, 'log_file_timed_rotation_when')
        self.assertEqual(1, config.logging.log_file_timed_rotation_interval, 'log_file_timed_rotation_interval')
        self.assertEqual(10, config.logging.log_files_to_keep, 'log_files_to_keep')
        self.assertIsNone(config.logging.log_file_timed_rotation_attime, 'log_file_timed_rotation_attime')
        self.assertFalse(config.logging.log_file_timed_rotation_utc, 'log_file_timed_rotation_utc')

        self.assertTrue(
            root_logger.level == logging.INFO,
            f"root logger level not INFO but {root_logger.level}"
        )
        my_module_log = logging.getLogger('my_module')
        self.assertTrue(
            my_module_log.level == logging.DEBUG,
            f"my_module_log logger level not DEBUG but {my_module_log.level}"
        )

        found_log_handlers = 0
        for handler in root_logger.handlers:
            if isinstance(handler, TimedRotatingFileHandler):
                found_log_handlers += 1
                self.assertIn(self.temp_dir, handler.baseFilename, 'log file name not correct')
                self.assertEqual(
                    config.logging.log_file_timed_rotation_when.upper(),
                    handler.when.upper(),
                    'when not set correctly'
                )
                self.assertEqual(config.logging.log_file_timed_rotation_utc, handler.utc, 'utc not set correctly')
                self.assertEqual(config.logging.log_file_timed_rotation_attime, handler.atTime, 'atTime not set correctly')
                self.assertEqual(config.logging.log_files_to_keep, handler.backupCount, 'atTime not set correctly')

        self.assertEqual(1, found_log_handlers, 'Did not find one RotatingFileHandler')

        my_module_log.debug('Test log entry')

        my_module_log.info('done')

    def test_timed_rot_file_handler_2(self):
        config = ConfigWithLogging(
            file_name='test_logging_timed_rot_file_2.ini',
            start_path=self.get_test_files_path(),
        )
        config.logging.setup_logging()
        root_logger = logging.getLogger()

        self.assertEqual(
            's'.upper(),
            config.logging.log_file_timed_rotation_when.upper(),
            'log_file_timed_rotation_when'
        )
        self.assertEqual(2, config.logging.log_file_timed_rotation_interval, 'log_file_timed_rotation_interval')
        self.assertEqual(100, config.logging.log_files_to_keep, 'log_files_to_keep')
        self.assertEqual(time(10, 45), config.logging.log_file_timed_rotation_attime, 'log_file_timed_rotation_attime')
        self.assertTrue(config.logging.log_file_timed_rotation_utc, 'log_file_timed_rotation_utc')

        self.assertTrue(
            root_logger.level == logging.INFO,
            f"root logger level not INFO but {root_logger.level}"
        )
        my_module_log = logging.getLogger('my_module')
        self.assertTrue(
            my_module_log.level == logging.DEBUG,
            f"my_module_log logger level not DEBUG but {my_module_log.level}"
        )

        found_log_handlers = 0
        for handler in root_logger.handlers:
            if isinstance(handler, TimedRotatingFileHandler):
                found_log_handlers += 1
                self.assertIn(self.temp_dir, handler.baseFilename, 'log file name not correct')
                self.assertEqual(
                    config.logging.log_file_timed_rotation_when.upper(),
                    handler.when.upper(),
                    'when not set correctly'
                )
                self.assertEqual(config.logging.log_file_timed_rotation_utc, handler.utc, 'utc not set correctly')
                self.assertEqual(config.logging.log_file_timed_rotation_attime, handler.atTime, 'atTime not set correctly')
                self.assertEqual(config.logging.log_files_to_keep, handler.backupCount, 'atTime not set correctly')

        self.assertEqual(1, found_log_handlers, 'Did not find one RotatingFileHandler')

        my_module_log.debug('Test log entry')

        my_module_log.info('done')
