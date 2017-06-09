# Project: PyUsbLamp
# Author: onelife

LOG_FILE_NAME = 'pyusblamp.log'


class AppLog(object):
   _instance = None
    
   def __new__(cls, *args, **kwargs):
      if not isinstance(cls._instance, cls):
         cls._instance = object.__new__(cls, *args, **kwargs)
      return cls._instance

   def __init__(self):
      from os import path
      logPath = path.join(path.abspath('.'), LOG_FILE_NAME)
      self.log = open(logPath, 'a+')

   def __del__(self):
      self.log.close()

   def Message(self, msg, echo=False):
      self.log.write(msg+'\n')
      if echo: print(msg)
      