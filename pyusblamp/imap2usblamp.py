# -*- coding: utf-8 -*-

# Project: PyUsbLamp
# Author: onelife

from optparse import OptionParser
from configparser import RawConfigParser, NoSectionError
from queue import SimpleQueue as Queue, Empty
from threading import Thread, Event
import sys
import re
from os import path
import imaplib

if sys.version_info >= (3,):
    from .pyusblamp import USBLamp
    from .applog import AppLog

    raw_input = input

    def encode(x):
        return x.encode("utf-8")

    def decode(x):
        return x.decode("utf-8")

else:
    from pyusblamp import USBLamp
    from applog import AppLog

    def encode(x):
        return x

    def decode(x):
        return x


DEBUG = 0
CONFIG_FILE_NAME = ".pyusblamp"
IMAP_SECTION = "IMAP_LIST"
CHECK_QUEUE_INTERVAL = DEBUG and 10 or 20
CHECK_EXIT_INTERVAL = 30
logger = AppLog().get_logger(__name__)
logger.setLevel(DEBUG and AppLog.DEBUG or AppLog.INFO)


class Imap2UsbLamp(object):
    def __init__(self, port):
        self.port = port
        self.usblamp = None
        self.pwd_queue = (Queue(), Queue())
        self.stop = Event()
        self.config_path = None
        self.parser = None
        self.config = {}
        self.get_config()

    def start_server(self, usblamp):
        self.usblamp = usblamp
        # create check_unseen and server threads
        t1 = Thread(target=self.check_unseen, args=(self, True))
        t1.daemon = True
        t1.start()
        t2 = Thread(target=self.server, args=(self,))
        t2.daemon = True
        t2.start()
        return (t1, t2)

    def get_config(self):
        # read config file
        self.config_path = path.expanduser(path.join("~", CONFIG_FILE_NAME))
        self.parser = RawConfigParser()
        if path.exists(self.config_path):
            self.parser.read(self.config_path)

        # read config and initialize if no content
        if not self.parser.has_section(IMAP_SECTION):
            self.parser.add_section(IMAP_SECTION)
        if self.parser.has_option(IMAP_SECTION, "Services"):
            try:
                services = eval(self.parser.get(IMAP_SECTION, "Services"))
                logger.debug("Service = %s" % (str(services)))
            except Exception as e:
                # no valid config
                logger.error(str(e))
                return

            # read each config
            fixed = False
            for s in services:
                self.config[s] = {}
                try:
                    for k in self.parser.options(s):
                        self.config[s][k] = self.parser.get(s, k)
                    # logger.debug("%s = %s" % (s, str(self.config[s])))
                except NoSectionError as e:
                    # missing config
                    logger.error(str(e))
                    services.remove(s)
                    self.parser.set(IMAP_SECTION, "Services", services)
                    self.config.pop(s)
                    fixed = True

            # save modification
            if fixed:
                with open(self.config_path, "wb") as f:
                    self.parser.write(f)
                    logger.info('*** Config file "%s" saved.' % self.config_path)

    def add_config(self, section):
        print("\nSetup IMAP service.\n")
        print("Please enter the following information for %s." % section)
        self.config[section] = {}
        self.config[section]["host"] = raw_input("Host: ").strip()
        self.config[section]["mailbox"] = raw_input("Mailbox: ").strip()
        self.config[section]["username"] = raw_input("Username: ").strip()
        # Oauth2
        while True:
            oauth = raw_input("Oauth2 (y/n): ").lower().strip()
            if oauth not in ["y", "n"]:
                print('Please enter "y" or "n" only.')
            else:
                break
        if oauth == "y":
            if sys.version_info >= (3,):
                from .oauth2 import GeneratePermissionUrl, AuthorizeTokens
            else:
                from oauth2 import GeneratePermissionUrl, AuthorizeTokens
            import webbrowser

            client_id = raw_input("Client ID: ").strip()
            secret = raw_input("Client Secret: ").strip()
            print('\nWeb browser will open soon. Please click "Allow access" and copy the verification code.\n')
            url = GeneratePermissionUrl(client_id)
            webbrowser.open(url, new=2)
            code = raw_input("Verification Code: ").strip()
            token = AuthorizeTokens(client_id, secret, code)
            logger.debug("Refresh Token: %s" % (token["refresh_token"]))
            logger.debug("Access Token: %s" % (token["access_token"]))
            logger.info("Access Token Expiration Seconds: %s" % (token["expires_in"]))
            self.config[section]["client_id"] = client_id
            self.config[section]["secret"] = secret
            self.config[section]["token"] = token
        # interval
        while True:
            try:
                self.config[section]["interval"] = int(raw_input("Refresh interval (in minutes): "))
                break
            except Exception:
                print("\nPlease enter an integer.\n")
        # color
        while True:
            color = raw_input("LED color in RR,GG,BB (0~%d): " % USBLamp.RGB_MAX).strip(",")
            done = 0
            try:
                for i in color.split(","):
                    i = int(i)
                    if 0 <= i <= USBLamp.RGB_MAX:
                        done += 1
                    else:
                        break
            except Exception:
                pass
            if done == 3:
                self.config[section]["color"] = "(" + color + ")"
                break
            else:
                print('\nPlease enter 3 integers (0~%d) separate by ",".\n' % USBLamp.RGB_MAX)
        # delay
        while True:
            try:
                self.config[section]["delay"] = float(eval("1.0*" + raw_input("Fading delay (0 for no fading): ")))
                break
            except Exception:
                print("\nPlease enter a floating number.\n")

        services = []
        if self.parser.has_option(IMAP_SECTION, "Services"):
            try:
                services = eval(self.parser.get(IMAP_SECTION, "Services"))
            except Exception:
                pass
        services.append(section)
        self.parser.set(IMAP_SECTION, "Services", services)
        self.parser.add_section(section)
        for k, v in self.config[section].items():
            self.parser.set(section, k, v)
        with open(self.config_path, "wb") as f:
            self.parser.write(f)
            logger.info('*** Config file "%s" saved.' % self.config_path)

    @staticmethod
    def check_unseen(imap, loop=False):
        from time import time

        if sys.version_info >= (3,):
            from .oauth2 import RefreshToken
            from .oauth2 import GenerateOAuth2String
        else:
            from oauth2 import RefreshToken
            from oauth2 import GenerateOAuth2String

        task = Queue()
        timeout_or_pwd = {}
        rx_pwd = {}

        # trigger all config
        for name, config in imap.config.items():
            if config.get("token"):
                # refresh token
                def refresh_token(config):
                    config["token"] = eval(config["token"])
                    config["token"] = RefreshToken(
                        config["clientid"],
                        config["secret"],
                        config["token"]["refresh_token"],
                    )
                    return time() + float(config["token"]["expires_in"]) - 1

                timeout_or_pwd[name] = refresh_token(config)
            else:
                timeout_or_pwd[name] = config.get("password", "")
            task.put(name)

        # process
        while True:
            # check if got password
            try:
                config_name, pwd = imap.pwd_queue[0].get(block=False)
                rx_pwd[config_name] = pwd
            except Empty:
                # check if got config
                try:
                    config_name = task.get(block=False)
                except Empty:
                    # do delay and check if stop
                    if imap.stop.wait(CHECK_QUEUE_INTERVAL):
                        break
                    else:
                        continue

            # access imap
            unseen = 0
            invalid_pwd = False
            config = imap.config[config_name]
            mailbox = None
            if config.get("token"):
                # oauth
                if time() > timeout_or_pwd[config_name]:
                    timeout_or_pwd[config_name] = refresh_token(config)
                auth_string = GenerateOAuth2String(config["username"], config["token"]["access_token"], False)
                mailbox = imaplib.IMAP4_SSL(config["host"])
                if DEBUG > 1:
                    mailbox.debug = 4
                mailbox.authenticate("XOAUTH2", lambda x: auth_string)
            else:
                # non-oauth
                if timeout_or_pwd[config_name]:
                    mailbox = imaplib.IMAP4_SSL(config["host"])
                    if DEBUG > 1:
                        mailbox.debug = 4
                    mailbox.login(config["username"], timeout_or_pwd[config_name])
                else:
                    logger.debug("%s, Waiting password." % config_name)
                    try:
                        if rx_pwd.get(config_name, ""):
                            pwd = rx_pwd.pop(config_name)
                            mailbox = imaplib.IMAP4_SSL(config["host"])
                            if DEBUG > 1:
                                mailbox.debug = 4
                            mailbox.login(config["username"], pwd)
                            timeout_or_pwd[config_name] = pwd
                            imap.pwd_queue[1].put("OK for %s" % config_name)
                        else:
                            invalid_pwd = True
                    except (imaplib.IMAP4.abort, imaplib.IMAP4.error):
                        imap.pwd_queue[1].put("%s Error: Wrong password!" % config_name)
                        invalid_pwd = True
                    except Exception as e:
                        imap.pwd_queue[1].put("%s Error: %s!" % (config_name, str(e)))
                        invalid_pwd = True

            if not invalid_pwd:
                # check status
                if config.get("search"):
                    mailbox.select(config["mailbox"])
                    typ, data = mailbox.search(None, config["search"])
                    if typ == "OK":
                        unseen = len(data[0].split())
                        logger.info("%s: %d messages match '%s'" % (config_name, unseen, config["search"]))
                else:
                    typ, data = mailbox.status(config["mailbox"], "(Messages UnSeen)")
                    if typ == "OK":
                        total, unseen = re.search(r"Messages\s+(\d+)\s+UnSeen\s+(\d+)", decode(data[0]), re.I).groups()
                        unseen = int(unseen)
                        logger.info("%s: %s messages and %s unseen" % (config_name, total, unseen))

                # control usblamp
                if unseen:
                    delay = float(config["delay"])
                    color = eval(config["color"])
                    if delay:
                        imap.usblamp.start_fading(delay, color)
                    else:
                        imap.usblamp.set_color(color)
                else:
                    imap.usblamp.off()

                delay = float(config["interval"]) * (1 if DEBUG else 60)
            else:
                delay = CHECK_QUEUE_INTERVAL

            if mailbox:
                mailbox.logout()
            if not loop:
                break
            # do delay and check if stop
            if imap.stop.wait(delay):
                break
            else:
                # schedule next check
                task.put(config_name)
        logger.debug("*** check_unseen thread exited.")

    @staticmethod
    def server(imap):
        import socket

        no_pwd = [k for k, v in imap.config.items() if not v.get("token") and not v.get("password")]
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_address = ("localhost", imap.port)
        try:
            sock.bind(server_address)
        except Exception as e:
            logger.error(str(e))
            imap.stop.set()
            raise
        logger.info("*** Server started on %s" % str(server_address))
        sock.listen(1)
        stop = False

        while not stop and not imap.stop.is_set():
            conn, client_address = sock.accept()
            logger.info("Server get connection from %s" % str(client_address))
            try:
                while True:
                    data = decode(conn.recv(64))
                    if not data:
                        break
                    if "password" in data.lower():
                        temp = ",".join(data.split(",")[:2])
                        logger.info("Server received %s,xxx" % temp)
                    else:
                        logger.info("Server received %s" % data)
                    msg = ""
                    if data == "stop":
                        conn.sendall(encode("ok"))
                        stop = True
                        break
                    elif data == "status":
                        for k, v in imap.config.items():
                            if k in no_pwd:
                                msg += "%s: Waiting password for %s\n" % (
                                    k,
                                    v["username"],
                                )
                            else:
                                msg += "%s: Working\n" % k
                    elif str.startswith(data.lower(), "password"):
                        data = data.split(",")
                        if data[1] not in no_pwd:
                            msg += "%s is not a valid config name.\n" % data[1]
                        else:
                            imap.pwd_queue[0].put(data[1:3])
                            ret = imap.pwd_queue[1].get()
                            if str.startswith(ret, "OK"):
                                no_pwd.remove(data[1])
                            msg += ret
                    elif data == "exit":
                        break
                    if msg:
                        conn.sendall(encode(msg))
            finally:
                conn.close()

        sock.close()
        logger.debug("*** server thread exited.")
        if stop:
            imap.usblamp.exit()
            imap.stop.set()

    @staticmethod
    def client(port):
        import socket

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_address = ("localhost", port)
        try:
            sock.connect(server_address)
        except socket.error:
            print("\nPlease start server first.\n")
            sys.exit()

        try:
            while True:
                print("\nImap2UsbLamp Status:\n")
                sock.sendall(encode("status"))
                print(decode(sock.recv(1024)))
                cmd = raw_input("Command: ").replace(" ", "").lower()
                if cmd == "stop":
                    sock.sendall(encode(cmd))
                    print("\n" + decode(sock.recv(1024)))
                    break
                elif cmd == "exit":
                    sock.sendall(encode(cmd))
                    break
                elif cmd == "password":
                    import getpass

                    while True:
                        try:
                            cfg = int(raw_input("IMAP_?: ").replace(" ", ""))
                            break
                        except Exception:
                            print("\nPlease enter an integer.\n")
                    pwd = getpass.getpass()
                    cfg = str(cfg)
                    sock.sendall(encode((",".join([cmd, "IMAP_" + cfg, pwd]))))
                    print("\n" + decode(sock.recv(1024)))
        finally:
            sock.close()
            sys.exit()


def imap2usblamp():
    # options
    parser = OptionParser(usage="usage: %prog [--status | --add | --show | --port | --log]")
    parser.add_option(
        "-t",
        "--status",
        action="store_true",
        dest="status",
        default=False,
        help="Check the server status",
    )
    parser.add_option(
        "-a",
        "--add",
        action="store_true",
        dest="add",
        default=False,
        help="Add an IMAP config",
    )
    parser.add_option(
        "-s",
        "--show",
        action="store_true",
        dest="show",
        default=False,
        help="Show current IMAP config",
    )
    parser.add_option(
        "-p",
        "--port",
        action="store",
        type="int",
        dest="port",
        default=8888,
        help="Port to listen",
    )
    parser.add_option(
        "-l",
        "--log",
        action="store_true",
        dest="log",
        default=False,
        help="Enable application log",
    )
    (options, _) = parser.parse_args()

    if options.log:
        AppLog().enable_logfile()
    logger.debug("options %s" % options)

    imap = Imap2UsbLamp(options.port)
    done = False

    # start client thread and exit
    if options.status:
        Thread(target=imap.client, args=(options.port,)).start()
        sys.exit()
    # add first config and exit
    if not imap.config:
        imap.add_config("IMAP_1")
        done = True
    # add a config and exit
    elif options.add:
        section = "IMAP_" + str(int(sorted(imap.config.keys())[-1].split("_")[1]) + 1)
        imap.add_config(section)
        done = True
    # show config and exit
    if options.show:
        for n, c in imap.config.items():
            print("%s:" % n)
            for k, v in c.items():
                print("\t%s = %s" % (k, v))
        done = True

    if done:
        sys.exit()

    # start server
    try:
        usblamp = USBLamp(lambda: imap.stop.set())
    except Exception as e:
        logger.error(str(e))
        sys.exit()
    t1, t2 = imap.start_server(usblamp)

    # wait to exit
    imap.stop.wait()
    t1.join()
    t2.join()
    sys.exit()


if DEBUG and __name__ == "__main__":
    imap2usblamp()
