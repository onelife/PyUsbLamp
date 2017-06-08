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

DEBUG = 0
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
         # Oauth2
         while True:
            oauth = raw_input('Oauth2 (y/n): ').lower().strip()
            if oauth not in ['y', 'n']:
               print('Please enter "y" or "n" only.')
            else:
               break
         if oauth == 'n':
            self.config[section]['password'] = getpass.getpass()
         else:
            from oauth2 import GeneratePermissionUrl, AuthorizeTokens
            import webbrowser
            clientId = raw_input('Client ID: ').strip()
            secret = raw_input('Client secret: ').strip()
            print('\nWeb brower will open soon. Please click "Allow access" and copy the verification code.\n')
            url = GeneratePermissionUrl(clientId)
            webbrowser.open(url, new=2)
            code = raw_input('Verification Code: ').strip()
            token = AuthorizeTokens(clientId, secret, code)
            if DEBUG: print("IMAP: Refresh Token: %s" % (token['refresh_token']))
            if DEBUG: print("IMAP: Access Token: %s" % (token['access_token']))
            if DEBUG: print("IMAP: Access Token Expiration Seconds: %s" % (token['expires_in']))
            self.config[section]['clientId'] = clientId
            self.config[section]['secret'] = secret
            self.config[section]['token'] = token
         # interval
         while True:
            try:
               self.config[section]['interval'] = int(raw_input('Refresh interval (in minutes): '))
               break
            except:
               print('\nPlease enter an integer.\n')
         # color
         while True:
            color  = raw_input('LED color in RR,GG,BB (0~%d): ' % (USBLamp.RGB_MAX)).strip(',')
            done = 0
            try:
               for i in color.split(','):
                  i = int(i)
                  if 0 <= i <= USBLamp.RGB_MAX:
                     done += 1
                  else:
                     break
            except:
               pass
            if done == 3:
               self.config[section]['color'] = '(' + color + ')'
               break
            else:
               print('\nPlease enter 3 integers (0~%d) separate by ",".\n' % (USBLamp.RGB_MAX))
         # delay
         while True:
            try:
               self.config[section]['delay'] = float(eval('1.0*' + raw_input('Fading delay (0 for no fading): ')))
               break
            except:
               print('\nPlease enter a floating number.\n')
         
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
      from time import time
      # refresh token
      if imap.has_key('token'):
         def refreshToken():
            from oauth2 import RefreshToken
            imap['token'] = eval(imap['token'])
            imap['token'] = RefreshToken(imap['clientid'], imap['secret'], imap['token']['refresh_token'])
            return time() + float(imap['token']['expires_in']) - 1
         expiryTime = refreshToken()

      # preprocess
      delay = float(imap['delay'])
      color = eval(imap['color'])
      # process
      while True:
         # access imap
         unseen = 0
         mailbox = imaplib.IMAP4_SSL(imap['host'])
         if DEBUG > 1: mailbox.debug = 4
         if imap.has_key('token'):
            if time() > expiryTime:
               expiryTime = refreshToken()
            from oauth2 import GenerateOAuth2String
            auth_string = GenerateOAuth2String(imap['username'], imap['token']['access_token'], False)
            mailbox.authenticate('XOAUTH2', lambda x: auth_string)
         else:
            mailbox.login(imap['username'], imap['password'])
         
         if imap.has_key('search'):
            mailbox.select(imap['mailbox'])
            typ, data = mailbox.search(None, imap['search'])
            if typ == 'OK':
               unseen = len(data[0].split())
               if DEBUG: print("IMAP: %s: %d messages match '%s'" % (imap['username'], unseen, imap['search']))
         else:
            typ, data = mailbox.status(imap['mailbox'],'(Messages UnSeen)')
            if typ == 'OK':
               total, unseen = re.search('Messages\s+(\d+)\s+UnSeen\s+(\d+)', data[0], re.I).groups()
               unseen = int(unseen)
               if DEBUG: print("IMAP: %s: %s messages and %s unseen" % (imap['username'], total, unseen))

         # control usblamp
         if unseen:
            if delay:
               usblamp.setFading(delay, color)
            else:
               usblamp.setFading(delay, color)
         else:
            usblamp.switchOff()
            
         mailbox.logout()
         
         if not loop:
            break
         sleep(float(imap['interval']))
         if usblamp.error:
            break
      

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
         if USBLamp.error:
            raise USBLamp.error
      except (KeyboardInterrupt, SystemExit):
         usblamp.switchOff()
         exit()

   