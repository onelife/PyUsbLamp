# Project: PyUsbLamp
# Author: onelife

from optparse import OptionParser
from time import sleep
from queue import Queue, Empty
from threading import Thread

import usb.core
import usb.backend.libusb1

DEBUG = 0
STEPS = 32

# R+2G+4B -> riso kagaku color index
riso_kagaku_tbl = (
    0, # [0] black 
    2, # [1] red 
    1, # [2] green 
    5, # [3] yellow 
    3, # [4] blue 
    6, # [5] magenta 
    4, # [6] cyan 
    7  # [7] white 
)
RISO_KAGAKU_IX = lambda r, g, b: riso_kagaku_tbl[(r and 1 or 0)+(g and 2 or 0)+(b and 4 or 0)]


def getSteps(maxValue, steps):
   x = range(0, maxValue + 1, max(1, maxValue / (steps - 1)))
   if len(x) >= steps:
      x = x[:steps - 1]
      x.append(maxValue)
   else:
      x.extend([maxValue] * (steps - len(x)))
   return x

def fading(lamp):
   print 'fading thread start'
   step = 0
   dir = 1
   idle = True
   while True:
      try:
         delay, newColor = lamp.queue.get(block=idle)
         if delay <= 0: 
            idle = True
            if newColor is not None:
               lamp.setColor(newColor)
            continue
         elif lamp.led_type == 1:
            idle = False
            r = getSteps(newColor[0], STEPS)
            g = getSteps(newColor[1], STEPS)
            b = getSteps(newColor[2], STEPS)
            state = zip(r, g, b)
      except Empty:
         pass
      
      sleep(delay)
      if lamp.led_type == 1:
         # Do fading
         lamp.setColor(state[step])
         step += dir
         if step == STEPS - 1 or step == 0:
            dir = -dir
      elif lamp.led_type == 2:
         setColor(newColor)
   print 'fading thread exit'


class USBLamp(object):
   ENDPOINT       = 0x81
   ID_VENDOR      = 0x1d34
   ID_PRODUCT_OLD = 0x0004
   ID_PRODUCT_NEW = 0x000a
   ID_VENDOR_2    = 0x1294
   ID_PRODUCT_2   = 0x1320
   RGB_MAX        = 0x40

   def send(self, bytes):
      # int result = 0;
      # int timeout = 1000;    // ms

      if self.led_type == 1:
         if DEBUG: print("USBLamp: send(%d) %02X %02X %02X %02X %02X %02X %02X %02X" % (len(bytes), bytes[0], bytes[1], bytes[2], bytes[3], bytes[4], bytes[5] ,bytes[6], bytes[7]))
         # requesttype = USB_TYPE_CLASS | USB_RECIP_INTERFACE
         # request = USB_REQ_SET_CONFIGURATION
         # value = 0x200
         # index = 0x00
         # timeout = 1000
         ret = self.lamp.ctrl_transfer(0x21, 0x09, 0x200, 0x00, bytes, 1000)
      elif self.led_type == 2:
         if DEBUG: print("USBLamp: send(%d) %02X %02X %02X %02X %02X" % (len(bytes), bytes[0], bytes[1], bytes[2], bytes[3], bytes[4]))
         ret = self.lamp.write(0x02, bytes, 1000)

      if (ret != len(bytes)):
         print("USBLamp Error: %d VS. %d" % (ret, len(bytes)));
   
   def __init__(self):
      import sys
      if sys.platform != 'win32':
         raise NotImplementedError('Currently, only MS Windows is supported!')
         
      from os import path
      import re
      backend = usb.backend.libusb1.get_backend(find_library=lambda x: path.join(
         path.abspath(path.dirname(__file__)), 
         'libusb', 
         'MS' + re.search('(\d+) bit', sys.version).groups()[0], 
         'dll', 'libusb-1.0.dll'))
      
      self.led_type = -1
      self.lamp  = None
      self.color = (0, 0, 0)
      self.queue = Queue()
      
      # get device
      while True:
         devs = list(usb.core.find(idVendor=self.ID_VENDOR, idProduct=self.ID_PRODUCT_NEW, find_all=True,backend=backend))
         if devs:
            self.led_type = 1
            if DEBUG: print("USBLamp: idVendor %d, idProduct %d" % (self.ID_VENDOR, self.ID_PRODUCT_NEW))
            break
         devs = list(usb.core.find(idVendor=self.ID_VENDOR, idProduct=self.ID_PRODUCT_OLD, find_all=True,backend=backend))
         if devs:
            self.led_type = 1
            if DEBUG: print("USBLamp: idVendor %d, idProduct %d" % (self.ID_VENDOR, self.ID_PRODUCT_OLD))
            break
         devs = list(usb.core.find(idVendor=self.ID_VENDOR_2, idProduct=self.ID_PRODUCT_2, find_all=True,backend=backend))
         if devs:
            self.led_type = 2
            if DEBUG: print("USBLamp: idVendor %d, idProduct %d" % (self.ID_VENDOR_2, self.ID_PRODUCT_2))
         break
      if DEBUG: print("USBLamp: LED Type is %d" % (self.led_type))
      self.lamp = devs[0]

      # send init cmd
      if self.led_type == 1:
         self.send((0x1f, 0x02, 0x00, 0x2e, 0x00, 0x00, 0x2b, 0x03))
         self.send((0x00, 0x02, 0x00, 0x2e, 0x00, 0x00, 0x2b, 0x04))
         self.send((0x00, 0x02, 0x00, 0x2e, 0x00, 0x00, 0x2b, 0x05))
         
      # create thread for fading
      t = Thread(target=fading, args=(self, ))
      t.daemon = True
      t.start()
            
   def getColor(self):
      return self.color
      
   def setColor(self, newColor):
      self.color = newColor
      if DEBUG: print("USBLamp: Set color %s" % str(self.color));

      if self.led_type == 1:
         self.send(self.color + (0x00, 0x00, 0x00, 0x00, 0x05))
      elif self.led_type == 2:
         self.send(RISO_KAGAKU_IX(*color) + (0x00, 0x00, 0x00, 0x00))
         
   def setFading(self, delay, newColor):
      self.color = newColor
      if DEBUG: print("USBLamp: Set fading %f,%s" % (delay, str(self.color)));
      self.queue.put((delay, newColor))

   def switchOff(self):
      self.setColor((0,0,0));
     
     

def main():
   l = USBLamp()
   print l.getColor()
   l.setFading(1.0/200, (0x40, 0x40, 0x40))
   sleep(10)
   l.setFading(0, (0x0, 0x0, 0x40))
   sleep(1)
   l.setFading(1.0/400, (0x0, 0x0, 0x40))
   sleep(10)
   l.setFading(0, (0x0, 0x40, 0x0))
   