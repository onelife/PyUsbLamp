# Project: PyUsbLamp
# Author: onelife

import logging

CONSOLE_LOGGER_NAME = 'log'
LOG_FILE_NAME = 'pyusblamp.log'


class AppLog(object):
    from logging import CRITICAL, ERROR, WARNING, INFO, DEBUG
    _cls_dict = {}

    def __new__(cls, *args, **kwargs):
        obj = object.__new__(cls, *args, **kwargs)
        obj.__dict__ = cls._cls_dict
        return obj

    def __init__(self):
        if self.__dict__.get('logger', None):
            return

        import sys
        self.logger = logging.getLogger('')
        self.logger.setLevel(logging.DEBUG)
        self.console = logging.StreamHandler(stream=sys.stdout)
        self.console.set_name(CONSOLE_LOGGER_NAME)
        self.console.setLevel(logging.DEBUG)
        self.console.setFormatter(logging.Formatter(
            fmt='[%(asctime)s] %(levelname)s [%(filename)s->%(funcName)s:%(lineno)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'))
        self.logger.addHandler(self.console)

    def enable_logfile(self):
        from os import path
        log_file = logging.FileHandler(path.join(path.abspath('.'), LOG_FILE_NAME), 'w')
        log_file.setLevel(logging.DEBUG)
        log_file.setFormatter(logging.Formatter(
            fmt='[%(asctime)s] %(levelname)s [%(filename)s->%(funcName)s:%(lineno)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'))
        self.logger.addHandler(log_file)

    def get_logger(self, name):
        return logging.getLogger(CONSOLE_LOGGER_NAME).getChild(name)
