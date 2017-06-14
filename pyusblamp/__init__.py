__author__ = 'onelife'
__license__ = "GPLv3"
__version__ = '1.15'

__setup = False
__depth = 1

import sys
from os import path

while True:
   try:
      stack = sys._getframe(__depth)
      __depth += 1
   except:
      break

__setup = path.basename(stack.f_globals.get('__file__')) == 'setup.py'

if not __setup:
   from .pyusblamp import *
   from .imap2usblamp import *