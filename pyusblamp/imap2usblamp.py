# Project: PyUsbLamp
# Author: onelife

from optparse import OptionParser
from configparser import RawConfigParser, NoSectionError
from queue import Queue, Empty
from threading import Thread, Timer
import sys
import re
from time import sleep

import imaplib

if sys.version_info >= (3, ):
   from .pyusblamp import USBLamp, USBError
   from .applog import AppLog
   raw_input = input
   encode = lambda x: x.encode("utf-8")
   decode = lambda x: x.decode("utf-8")
else:
   from pyusblamp import USBLamp, USBError
   from applog import AppLog
   encode = lambda x: x
   decode = lambda x: x

DEBUG = 0
CONFIG_FILE_NAME = '.pyusblamp'
IMAP_SECTION = 'IMAP_LIST'
CHECK_QUEUE_INTERVAL = DEBUG and 10 or 20
LogMsg = AppLog().Message


class Imap2UsbLamp(object):
   def __init__(self, port):
      self.log = DEBUG
      self.port = port
      self.usblamp = None
      self.pwdQueue = (Queue(), Queue())
      self.getConfig()

   def startServer(self,  usblamp):
      self.usblamp = usblamp
      # create threads for checkUnseen and server
      t1 = Thread(target=self.checkUnseen, args=(self, True))
      t1.daemon = True
      t1.start()
      t2 = Thread(target=self.server, args=(self,))
      t2.daemon = True
      t2.start()
   
   def getConfig(self):
      from os import path
      self.cfgPath = path.expanduser(path.join('~', CONFIG_FILE_NAME))
      self.parser = RawConfigParser()
      if path.exists(self.cfgPath):
         self.parser.read(self.cfgPath) 
         
      if not self.parser.has_section(IMAP_SECTION):
         self.parser.add_section(IMAP_SECTION)
         
      self.config = {}
      if self.parser.has_option(IMAP_SECTION, 'Services'):
         try:
            services = eval(self.parser.get(IMAP_SECTION, 'Services'))
            if self.log: LogMsg("IMAP: Service = %s" % (str(services)), DEBUG)
            for s in services:
               self.config[s] = {}
               for k in self.parser.options(s):
                  self.config[s][k] = self.parser.get(s, k)
               if self.log: LogMsg("IMAP: %s = %s" % (s, str(self.config[s])), DEBUG)
         except NoSectionError as e:
            print('\n%s' % (e.message))
            services.remove(s)
            self.parser.set(IMAP_SECTION, 'Services', services)
            self.config.pop(s)
            with open(self.cfgPath, 'wb') as f:
               self.parser.write(f)
               print('\nIMAP: Config file "%s" saved.' % (self.cfgPath))
         except:
            self.config = {}

   def addConfig(self, section):
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
         if oauth == 'y':
            if sys.version_info >= (3, ):
               from .oauth2 import GeneratePermissionUrl, AuthorizeTokens
            else:
               from oauth2 import GeneratePermissionUrl, AuthorizeTokens
            import webbrowser
            clientId = raw_input('Client ID: ').strip()
            secret = raw_input('Client Secret: ').strip()
            print('\nWeb browser will open soon. Please click "Allow access" and copy the verification code.\n')
            url = GeneratePermissionUrl(clientId)
            webbrowser.open(url, new=2)
            code = raw_input('Verification Code: ').strip()
            token = AuthorizeTokens(clientId, secret, code)
            if self.log: LogMsg("IMAP: Refresh Token: %s" % (token['refresh_token']), DEBUG)
            if self.log: LogMsg("IMAP: Access Token: %s" % (token['access_token']), DEBUG)
            if self.log: LogMsg("IMAP: Access Token Expiration Seconds: %s" % (token['expires_in']), DEBUG)
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
         
         services = []
         if self.parser.has_option(IMAP_SECTION, 'Services'):
            try:
               services = eval(self.parser.get(IMAP_SECTION, 'Services'))
            except:
               pass
         services.append(section)
         self.parser.set(IMAP_SECTION, 'Services', services)
         self.parser.add_section(section)
         for k, v in self.config[section].items():
            self.parser.set(section, k, v)
         with open(self.cfgPath, 'wb') as f:
            self.parser.write(f)
            print('\nIMAP: Config file "%s" saved.' % (self.cfgPath))

   @staticmethod
   def checkUnseen(imap, loop=False): 
      from time import time
      if sys.version_info >= (3, ):
         from .oauth2 import RefreshToken
         from .oauth2 import GenerateOAuth2String
      else:
         from oauth2 import RefreshToken
         from oauth2 import GenerateOAuth2String
      
      task = Queue()
      timeoutOrPwd = {}
      rxPwd = {}
      for name, config in imap.config.items():
         # preprocess
         if config.get('token'):
            # refresh token
            def refreshToken(config):
               config['token'] = eval(config['token'])
               config['token'] = RefreshToken(config['clientid'], config['secret'], config['token']['refresh_token'])
               return time() + float(config['token']['expires_in']) - 1
            timeoutOrPwd[name] = refreshToken(config)
         else:
            timeoutOrPwd[name] = config.get('password', '')

         t = Timer(CHECK_QUEUE_INTERVAL, lambda x: task.put(x), args=(name,))
         t.start()
         
      # process
      while True:
         try:
            cfgName, pwd = imap.pwdQueue[0].get(block=False)
            rxPwd[cfgName] = pwd
         except Empty:
            try:
               cfgName = task.get(block=False)
            except Empty:
               sleep(CHECK_QUEUE_INTERVAL)
               continue
         # access imap
         unseen = 0
         waitPwd = False
         config = imap.config[cfgName]
         mailbox = imaplib.IMAP4_SSL(config['host'])
         if DEBUG > 1: mailbox.debug = 4
         if config.get('token'):
            if time() > timeoutOrPwd[cfgName]:
               timeoutOrPwd[cfgName] = refreshToken(config)
            auth_string = GenerateOAuth2String(config['username'], config['token']['access_token'], False)
            mailbox.authenticate('XOAUTH2', lambda x: auth_string)
         else:
            if timeoutOrPwd[cfgName]:
               mailbox.login(config['username'], timeoutOrPwd[cfgName])
            else:
               if imap.log: LogMsg("IMAP: %s, Waiting password." % (cfgName), DEBUG)
               try:
                  if rxPwd.get(cfgName, ''):
                     pwd = rxPwd.pop(cfgName)
                     mailbox.login(config['username'], pwd)
                     timeoutOrPwd[cfgName] = pwd
                     imap.pwdQueue[1].put('OK for %s' % (cfgName))
                  else:
                     waitPwd = True
               except (imaplib.IMAP4.abort, imaplib.IMAP4.error):
                  imap.pwdQueue[1].put('Wrong password for %s!' % (cfgName))
                  waitPwd = True
               except:
                  imap.pwdQueue[1].put('Unknown error for %s!' % (cfgName))
                  waitPwd = True

         if not waitPwd:
            # check status
            if config.get('search'):
               mailbox.select(config['mailbox'])
               typ, data = mailbox.search(None, config['search'])
               if typ == 'OK':
                  unseen = len(data[0].split())
                  if imap.log: LogMsg("IMAP: %s, %d messages match '%s'" % (cfgName, unseen, config['search']), DEBUG)
            else:
               typ, data = mailbox.status(config['mailbox'],'(Messages UnSeen)')
               if typ == 'OK':
                  total, unseen = re.search('Messages\s+(\d+)\s+UnSeen\s+(\d+)', decode(data[0]), re.I).groups()
                  unseen = int(unseen)
                  if imap.log: LogMsg("IMAP: %s, %s messages and %s unseen" % (cfgName, total, unseen), DEBUG)
            # control usblamp
            if unseen:
               delay = float(config['delay'])
               color = eval(config['color'])
               imap.usblamp.setFading(delay, color)
            else:
               imap.usblamp.switchOff()
            # schedule next check
            t = Timer(float(config['interval']) * (DEBUG and 1 or 60), lambda x: task.put(x), args=(cfgName,))
            t.start()
         else:
            t = Timer(CHECK_QUEUE_INTERVAL, lambda x: task.put(x), args=(cfgName,))
            t.start()
               
         mailbox.logout()
         if imap.usblamp.__class__.error:
            if imap.log: LogMsg("IMAP: CheckUnseen thread exited.", DEBUG)
            break
         if not loop:
            break
      
   @staticmethod
   def server(imap): 
      import socket
      noPwd = [k for k, v in imap.config.items() if not v.get('token') and not v.get('password')]
      sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
      server_address = ('localhost', imap.port)
      sock.bind(server_address)
      if imap.log: LogMsg("IMAP: Server started on %s" % str(server_address), DEBUG)
      sock.listen(1)
      
      while True:
         conn, client_address = sock.accept()
         if imap.log: LogMsg("IMAP: Server get connection from %s" % str(client_address), DEBUG)
         try:
            while True:
               data = decode(conn.recv(64))
               if not data: 
                  break
               if imap.log: 
                  if 'password' in data.lower():
                     temp = ','.join(data.split(',')[:2])
                     LogMsg("IMAP: Server received %s,xxx" % (temp), DEBUG)
                  else:
                     LogMsg("IMAP: Server received %s" % (data), DEBUG)
               msg = ''
               if data == 'stop':
                  imap.usblamp.exit()
                  msg += 'ok'
               elif data == 'status':
                  for k, v in imap.config.items():
                     if k in noPwd:
                        msg += '%s: Waiting password for %s\n' % (k, v['username'])
                     else:
                        msg += '%s: Working\n' % (k)
               elif str.startswith(data.lower(), 'password'):
                  data = data.split(',')
                  if data[1] not in noPwd:
                     msg += '%s is not a valid config name.\n' % (data[1])
                  else:
                     imap.pwdQueue[0].put(data[1:3])
                     ret = imap.pwdQueue[1].get()
                     if str.startswith(ret, 'OK'):
                        noPwd.remove(data[1])
                     msg += ret
               elif data == 'exit':
                  break
               if msg:
                  conn.sendall(encode(msg))
         finally:
            conn.close()

   @staticmethod
   def client(port):
      import socket
      sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
      server_address = ('localhost', port)
      try:
         sock.connect(server_address)
      except socket.error:
         print('\nPlease start server first.\n')
         sys.exit()
         
      try:
         while True:
            print('\nImap2UsbLamp Status:\n')
            sock.sendall(encode('status'))
            print(decode(sock.recv(1024)))
            cmd = raw_input('Command: ').replace(' ', '').lower()
            if cmd == 'stop':
               sock.sendall(encode(cmd))
               print('\n'+decode(sock.recv(1024)))
               break
            elif cmd == 'exit':
               sock.sendall(encode(cmd))
               break
            elif cmd == 'password':
               import getpass
               while True:
                  try:
                     cfg = int(raw_input('IMAP_?: ').replace(' ', ''))
                     break
                  except:
                     print('\nPlease enter an integer.\n')
               pwd = getpass.getpass()
               cfg = str(cfg)
               sock.sendall(encode((','.join([cmd, 'IMAP_' + cfg, pwd]))))
               print('\n'+decode(sock.recv(1024)))
      finally:
         sock.close()
         sys.exit()
         

def imap2usblamp():
   # options
   parser = OptionParser(usage="usage: %prog [--status | --add | --show | --port | --log]")
   parser.add_option("-t", "--status", action="store_true", dest="status", default = False, help='Check the server status')
   parser.add_option("-a", "--add", action="store_true", dest="add", default = False, help='Add an IMAP config')
   parser.add_option("-s", "--show", action="store_true", dest="show", default = False, help='Show current IMAP config')
   parser.add_option("-p", "--port", action="store", type="int", dest="port", default = 8888, help='Port to listen')
   parser.add_option("-l", "--log", action="store_true", dest="log", default = False, help='Enable application log')
   (options, _) = parser.parse_args()
   options.log = options.log and 1 or 0

   if DEBUG: print("IMAP: options %s" % (options))
   
   done = False
   imap = Imap2UsbLamp(options.port)
   imap.log = options.log
   
   if options.status:
      Thread(target=imap.client, args=(options.port,)).start()
      sys.exit()
      
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
      
   if done: sys.exit()
   
   usblamp = USBLamp()
   usblamp.log = options.log
   imap.startServer(usblamp)

   while True:
      try:
         sleep(60)
         if USBLamp.error:
            raise USBLamp.error
      except (KeyboardInterrupt, SystemExit, USBError):
         usblamp.exit()

         sys.exit()

if DEBUG and __name__ == '__main__':
   imap2usblamp()