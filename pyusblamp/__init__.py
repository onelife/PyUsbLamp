# -*- coding: utf-8 -*-

import sys
from os import path

__author__ = "onelife"
__license__ = "GPLv3"
__version__ = "1.40"

__setup = False
__depth = 1

while True:
    try:
        stack = sys._getframe(__depth)
        __depth += 1
        if path.basename(stack.f_globals.get("__file__")) == "setup.py":  # type: ignore
            __setup = True
            break
    except Exception:
        break

print(f"*** {__setup=}")

if not __setup:
    from .pyusblamp import *
    from .imap2usblamp import *
