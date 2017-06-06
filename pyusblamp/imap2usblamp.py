# Project: PyUsbLamp
# Author: onelife

from optparse import OptionParser
from ConfigParser import RawConfigParser
from threading import Thread
import re
from time import sleep
from sys import exit

import imaplib
from pyusblamp import USBLamp

DEBUG = 1
IMAP_SECTION = 'IMAP_LIST'


class Imap2UsbLamp(object):
   def __init__(self):
      self.getConfig()

   def getConfig(self):
      from os import path
      self.cfgPath = path.expanduser(path.join('~', '.pyusblamp'))
      self.parser = RawConfigParser()
      if path.exists(self.cfgPath):
         self.parser.read(self.cfgPath) 
         
      if not self.parser.has_section(IMAP_SECTION):
         self.parser.add_section(IMAP_SECTION)
         
      self.config = {}
      if self.parser.has_option(IMAP_SECTION, 'Services'):
         try:
            services = eval(self.parser.get(IMAP_SECTION, 'Services'))
            if DEBUG: print("IMAP: Service = %s" % (str(services)))
            for s in services:
               self.config[s] = {}
               for k in self.parser.options(s):
                  self.config[s][k] = self.parser.get(s, k)
               if DEBUG: print("IMAP: %s = %s" % (s, str(self.config[s])))
         except:
            self.config = {}

   def addConfig(self, section):
         import getpass
         print('\nSetup IMAP service.\n')
         print('Please enter the following informations for %s.' % (section))
         self.config[section] = {}
         self.config[section]['host'] = raw_input('Host: ').strip()
         self.config[section]['mailbox'] = raw_input('Mailbox: ').strip()
         self.config[section]['username'] = raw_input('Username: ').strip()
         self.config[section]['password'] = getpass.getpass()
         self.config[section]['interval'] = raw_input('Refresh interval (in minutes): ').strip()
         self.config[section]['color'] = raw_input('LED color in RR,GG,BB (0~64): ').strip()
         self.config[section]['delay'] = raw_input('Fading delay (0 for no fading): ').strip()
         
         if self.parser.has_option(IMAP_SECTION, 'Services'):
            try:
               services = eval(self.parser.get(IMAP_SECTION, 'Services'))
            except:
               services = []
         
         services.append(section)
         self.parser.set(IMAP_SECTION, 'Services', services)
         self.parser.add_section(section)
         for k, v in self.config[section].items():
            self.parser.set(section, k, v)
         with open(self.cfgPath, 'wb') as f:
            self.parser.write(f)
            print
            print('IMAP: Config file %s saved.' % (self.cfgPath))

   @staticmethod
   def checkUnseen(name, imap, usblamp, loop=False):
      while True:
         mailbox = imaplib.IMAP4_SSL(imap['host'])
         mailbox.login(imap['username'], imap['password'])
         unseen = 0
         
         typ, data = mailbox.status(imap['mailbox'],'(Messages UnSeen)')
         if typ == 'OK':
            total, unseen = re.search('Messages\s+(\d+)\s+UnSeen\s+(\d+)', data[0], re.I).groups()
            unseen = int(unseen)
            if DEBUG: print("IMAP: %s messages and %s unseen" % (total, unseen))

         if unseen:
            try:
               delay = float(eval(imap['delay']))
               color = eval('(' + imap['color'] + ')')
               if delay:
                  usblamp.setFading(delay, color)
               else:
                  usblamp.setFading(delay, color)
            except:
               raise SystemError('Bad LED setting in config %s!' % (name))
         else:
            usblamp.switchOff()

         mailbox.logout()
         
         if not loop:
            break
         try:
            interval = float(imap['interval'])
            sleep(interval)
         except:
            raise SystemError('Bad refresh interval setting in config %s!' % (name))
      

def imap2usblamp():
   # options
   parser = OptionParser(usage="usage: %prog [--add | --show]")
   parser.add_option("-a", "--add", action="store_true", dest="add", default = False, help='Add an IMAP config')
   parser.add_option("-s", "--show", action="store_true", dest="show", default = False, help='Show current IMAP config')
   (options, _) = parser.parse_args()

   if DEBUG: print("IMAP: options %s" % (options))
   
   done = False
   imap = Imap2UsbLamp()
   
   if not imap.config:
      imap.addConfig('IMAP_1')
      done = True
   elif options.add:
      section = 'IMAP_' + str(int(sorted(imap.config.keys())[-1].split('_')[1]) + 1)
      imap.addConfig(section)
      done = True
   if options.show:
      for n, c in imap.config.items():
         print('%s:' % (n))
         for k, v in c.items():
            print('\t%s = %s' % (k ,v))
      done = True
      
   if done: exit()
   
   usblamp = USBLamp()
   for k, v in imap.config.items():
      t = Thread(target=imap.checkUnseen, args=(k, v, usblamp, True))
      t.daemon = True
      t.start()
      
   while True:
      try:
         sleep(60)
      except (KeyboardInterrupt, SystemExit):
         usblamp.switchOff()
         exit()


imap2usblamp()
   