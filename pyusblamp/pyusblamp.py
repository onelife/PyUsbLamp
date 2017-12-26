# Project: PyUsbLamp
# Author: onelife

import sys
from six.moves.queue import Queue, Empty
from threading import Thread, Event

import usb.core
import usb.backend.libusb1
from usb.core import USBError

if sys.version_info >= (3,):
    from .applog import AppLog
else:
    from applog import AppLog


DEBUG = 0
STEPS = 32
logger = AppLog().get_logger(__name__)
logger.setLevel(DEBUG and AppLog.DEBUG or AppLog.INFO)


class USBLamp(object):
    ID_VENDOR = 0x1d34
    ID_PRODUCT = (0x000a, 0x0004)
    RGB_MAX = 0x40

    @staticmethod
    def get_steps(start, end, steps):
        if start == end:
            x = []
        else:
            delta = int((end - start) / float(steps - 1))
            if delta == 0:
                delta = 1 if start < end else -1
            x = list(range(start, end + 1, delta))
        if len(x) >= steps:
            x = x[:steps - 1]
            x.append(end)
        else:
            x.extend([end] * (steps - len(x)))
        return x

    @staticmethod
    def fading(lamp):
        step = 0
        direction = 1
        idle = True
        while True:
            # check exit condition
            if lamp.error.is_set():
                break

            # get task
            try:
                delay, from_color, to_color = lamp._task.get(block=idle)
                if delay <= 0:
                    continue
                from_color = tuple([max(0, min(lamp.RGB_MAX, c)) for c in from_color])
                to_color = tuple([max(0, min(lamp.RGB_MAX, c)) for c in to_color])
                idle = False
                r = lamp.get_steps(from_color[0], to_color[0], STEPS)
                g = lamp.get_steps(from_color[1], to_color[1], STEPS)
                b = lamp.get_steps(from_color[2], to_color[2], STEPS)
                state = list(zip(r, g, b))
            except Empty:
                pass

            # do delay and check if stop
            idle = lamp.stop.wait(delay)
            if idle:
                # reset color
                lamp.send(lamp._color + (0x00, 0x00, 0x00, 0x00, 0x05))
                continue

            # change color and update step
            lamp.send(state[step] + (0x00, 0x00, 0x00, 0x00, 0x05))
            step += direction
            if step == STEPS - 1 or step == 0:
                direction = -direction
        logger.debug("*** fading thread exited.")

    def send(self, data):
        # logger.debug("send(%d) %02X %02X %02X %02X %02X %02X %02X %02X" % (
        #     len(data), data[0], data[1], data[2], data[3], data[4], data[5], data[6], data[7]))
        try:
            # request_type = USB_TYPE_CLASS | USB_RECIP_INTERFACE
            # request = USB_REQ_SET_CONFIGURATION
            # value = 0x200
            # index = 0x00
            # timeout = 1000
            ret = self._lamp.ctrl_transfer(0x21, 0x09, 0x200, 0x00, data, 1000)
        except USBError as e:
            logger.error(str(e))
            self.error.set()
            if self.error_cb:
                self.error_cb()
            raise
        if ret != len(data):
            logger.error("Get %d VS. send %d" % (ret, len(data)))

    def __init__(self, error_cb=None):
        # initial backend
        if sys.platform == 'win32':
            from os import path
            import re
            backend = usb.backend.libusb1.get_backend(find_library=lambda x: path.join(
                path.dirname(__file__),
                'libusb',
                'MS' + re.search('(\d+) bit', sys.version).groups()[0],
                'dll', 'libusb-1.0.dll'))
        elif sys.platform.startswith('linux'):
            backend = None
        else:
            raise NotImplementedError('%s system is not supported!')

        # get device
        for pid in self.ID_PRODUCT:
            devs = list(usb.core.find(idVendor=self.ID_VENDOR, idProduct=pid, find_all=True, backend=backend))
            if devs:
                logger.info("idVendor %d, idProduct %d" % (self.ID_VENDOR, pid))
                break
        else:
            raise SystemError('No device found!')

        # initial lamp and color
        self._lamp = devs[0]
        if sys.platform.startswith('linux') and self._lamp.is_kernel_driver_active(0):
            self._reattach = True
            self._lamp.detach_kernel_driver(0)
        else:
            self._reattach = False
        self._color = (0, 0, 0)

        # error and exit event
        self.error = Event()
        self.error_cb = error_cb

        # send init cmd
        self.send((0x1f, 0x02, 0x00, 0x2e, 0x00, 0x00, 0x2b, 0x03))
        self.send((0x00, 0x02, 0x00, 0x2e, 0x00, 0x00, 0x2b, 0x04))
        self.send((0x00, 0x02, 0x00, 0x2e, 0x00, 0x00, 0x2b, 0x05))
        self.send(self._color + (0x00, 0x00, 0x00, 0x00, 0x05))

        # create stop event, fading task queue and daemon thread
        self.stop = Event()
        self._task = Queue()
        self._thread = Thread(target=self.fading, args=(self,))
        self._thread.daemon = True
        self._thread.start()

    def get_color(self):
        return self._color

    def set_color(self, new_color):
        self._color = tuple([max(0, min(self.RGB_MAX, c)) for c in new_color])
        logger.debug("Set color %s" % str(self._color))
        self.send(self._color + (0x00, 0x00, 0x00, 0x00, 0x05))

    def start_fading(self, delay, to_color, from_color=None):
        if not from_color:
            from_color = (0, 0, 0)
        logger.debug("Start fading with delay %f, %s ~ %s" % (delay, str(from_color), str(to_color)))
        self.stop.clear()
        self._task.put((delay, from_color, to_color))

    def stop_fading(self):
        logger.debug("Stop fading")
        self.stop.set()

    def off(self):
        self.stop.set()
        self.set_color((0, 0, 0))

    def exit(self):
        self._task.put((0, (0, 0, 0), (0, 0, 0)))
        self.stop.set()
        self.error.set()
        self._thread.join()
        self.off()
        usb.util.dispose_resources(self._lamp)
        if self._reattach:
            self._lamp.attach_kernel_driver(0)
        logger.debug("Exit!")
