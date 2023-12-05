# -*- coding: utf-8 -*-

# Project: PyUsbLamp
# Author: onelife

import logging
from typing import Any

CONSOLE_LOGGER_NAME = "log"
LOG_FILE_NAME = "pyusblamp.log"


class AppLog(object):
    from logging import CRITICAL, ERROR, WARNING, INFO, DEBUG

    _cls_dict: dict[str, Any] = {}

    def __new__(cls, *args, **kwargs):
        obj = object.__new__(cls, *args, **kwargs)
        obj.__dict__ = cls._cls_dict
        return obj

    def __init__(self):
        if self.__dict__.get("logger", None):
            return

        import sys

        # import colorlog
        #
        # console = colorlog.StreamHandler(stream=sys.stdout)
        # console.setFormatter(colorlog.ColoredFormatter(
        #     '%(log_color)s[%(asctime)s] %(levelname)s [%(filename)s->%(funcName)s:%(lineno)s] %(message)s',
        #     log_colors={
        #         'DEBUG': 'cyan',
        #         'INFO': 'green',
        #         'WARNING': 'yellow',
        #         'ERROR': 'red',
        #         'CRITICAL': 'red,bg_white',
        #     },
        #     datefmt='%Y-%m-%d %H:%M:%S'))
        console = logging.StreamHandler(stream=sys.stdout)
        console.setFormatter(
            logging.Formatter(
                fmt="[%(asctime)s] %(levelname)s [%(filename)s->%(funcName)s:%(lineno)s] %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        console.set_name(CONSOLE_LOGGER_NAME)
        console.setLevel(logging.DEBUG)

        # self.logger = colorlog.getLogger('')
        self.logger = logging.getLogger("")
        self.logger.setLevel(logging.DEBUG)
        self.logger.addHandler(console)

    def enable_logfile(self):
        from os import path

        log_file = logging.FileHandler(path.join(path.abspath("."), LOG_FILE_NAME), "w")
        log_file.setLevel(logging.DEBUG)
        log_file.setFormatter(
            logging.Formatter(
                fmt="[%(asctime)s] %(levelname)s [%(filename)s->%(funcName)s:%(lineno)s] %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        self.logger.addHandler(log_file)

    def get_logger(self, name):
        return logging.getLogger(CONSOLE_LOGGER_NAME).getChild(name)
