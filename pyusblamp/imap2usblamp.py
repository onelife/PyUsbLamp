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
THREAD_INTERVAL = 30
CHECK_PWD_INTERVAL = 30
LogMsg = AppLog().Message


class Imap2UsbLamp(object):
   def __init__(self):
      self.log = DEBUG
      self.getConfig()

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
   def checkUnseen(name, config, usblamp, log, queue=None, loop=False):
      from time import time
      # refresh token
      if config.get('token'):
         def refreshToken():
            if sys.version_info >= (3, ):
               from .oauth2 import RefreshToken
            else:
               from oauth2 import RefreshToken
            config['token'] = eval(config['token'])
            config['token'] = RefreshToken(config['clientid'], config['secret'], config['token']['refresh_token'])
            return time() + float(config['token']['expires_in']) - 1
         expiryTime = refreshToken()

      # preprocess
      delay = float(config['delay'])
      color = eval(config['color'])
      waitPwd = not config.get('token') and queue
      pwd = waitPwd and '' or config.get('password', '')
      # process
      while True:
         # access imap
         unseen = 0
         mailbox = imaplib.IMAP4_SSL(config['host'])
         if DEBUG > 1: mailbox.debug = 4
         if config.get('token'):
            if time() > expiryTime:
               expiryTime = refreshToken()
            if sys.version_info >= (3, ):
               from .oauth2 import GenerateOAuth2String
            else:
               from oauth2 import GenerateOAuth2String
            auth_string = GenerateOAuth2String(config['username'], config['token']['access_token'], False)
            mailbox.authenticate('XOAUTH2', lambda x: auth_string)
         elif not waitPwd:
            mailbox.login(config['username'], pwd)
         
         if waitPwd:
            if log: LogMsg("IMAP: Waiting for enter password.", DEBUG)
            try:
               pwd = queue[0].get(timeout = CHECK_PWD_INTERVAL)
               mailbox.login(config['username'], pwd)
               queue[1].put('ok')
               waitPwd = False
            except Empty:
               pass
            except (imaplib.IMAP4.abort, imaplib.IMAP4.error):
               queue[1].put('Wrong password!')
            except:
               queue[1].put('Unknown error!')
            if usblamp.__class__.error:
               if log: LogMsg("IMAP: CheckUnseen thread exited.", DEBUG)
               break
         
         if not waitPwd:
            if config.get('search'):
               mailbox.select(config['mailbox'])
               typ, data = mailbox.search(None, config['search'])
               if typ == 'OK':
                  unseen = len(data[0].split())
                  if log: LogMsg("IMAP: %s, %d messages match '%s'" % (name, unseen, config['search']), DEBUG)
            else:
               typ, data = mailbox.status(config['mailbox'],'(Messages UnSeen)')
               if typ == 'OK':
                  total, unseen = re.search('Messages\s+(\d+)\s+UnSeen\s+(\d+)', decode(data[0]), re.I).groups()
                  unseen = int(unseen)
                  if log: LogMsg("IMAP: %s, %s messages and %s unseen" % (name, total, unseen), DEBUG)

            # control usblamp
            if unseen:
               usblamp.setFading(delay, color)
            else:
               usblamp.switchOff()

            mailbox.logout()
            if not loop:
               break
            if usblamp.__class__.error:
               if log: LogMsg("IMAP: CheckUnseen thread exited.", DEBUG)
               break
            sleep(float(config['interval']) * (DEBUG and 1 or 60))
      
   @staticmethod
   def server(config, port, usblamp, log, pwdQueue=None): 
      import socket
      noPwd = [k for k, v in config.items() if not v.get('token') and not v.get('password')]
      sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
      server_address = ('localhost', port)
      sock.bind(server_address)
      if log: LogMsg("IMAP: Server started on %s" % str(server_address), DEBUG)
      sock.listen(1)
      
      while True:
         conn, client_address = sock.accept()
         if log: LogMsg("IMAP: Server get connection from %s" % str(client_address), DEBUG)
         try:
            while True:
               data = decode(conn.recv(64))
               if not data: 
                  break
               if log: LogMsg("IMAP: Server received %s" % (data), DEBUG)
               msg = ''
               if data == 'stop':
                  usblamp.exit()
                  msg += 'ok'
               elif data == 'status':
                  for k, v in config.items():
                     if k in noPwd:
                        msg += '%s: Waiting password for %s\n' % (k, v['username'])
                     else:
                        msg += '%s: Working\n' % (k)
               elif str.startswith(data.lower(), 'password'):
                  data = data.split(',')
                  cfg, pwd = data[1:3]
                  if cfg not in noPwd:
                     msg += '%s is not a valid config name.\n' % (cfg)
                  else:
                     pwdQueue[cfg][0].put(pwd)
                     ret = pwdQueue[cfg][1].get()
                     if ret == 'ok':
                        noPwd.remove(cfg)
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
               sys.exit()
            elif cmd == 'exit':
               sock.sendall(encode(cmd))
               sys.exit()
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
   imap = Imap2UsbLamp()
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
   i = 0
   workers = []
   pwdQueue = {}
   for k, v in imap.config.items():
      if not v.get('token') and not v.get('password'):
         pwdQueue[k] = (Queue(), Queue())
      workers.append(Timer(THREAD_INTERVAL * i, imap.checkUnseen, args=(k, v, usblamp, options.log, pwdQueue.get(k, None), True)))
      workers[-1].start()
      i += 1
  
   t = Thread(target=imap.server, args=(imap.config, options.port, usblamp, options.log, pwdQueue))
   t.daemon = True
   t.start()

   while True:
      try:
         sleep(60)
         if USBLamp.error:
            raise USBLamp.error
      except (KeyboardInterrupt, SystemExit, USBError):
         usblamp.exit()
         for w in workers:
            w.join()
         sys.exit()

if DEBUG and __name__ == '__main__':
   imap2usblamp()