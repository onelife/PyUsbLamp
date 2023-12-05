# -*- coding: utf-8 -*-

from setuptools import setup, find_packages  # type: ignore
from sys import platform
from os import path
import pyusblamp


with open(path.join(".", "README.md"), encoding="utf-8") as f:
    long_description = f.read()

with open("requirements.txt", encoding="utf-8") as f:
    install_requires = [
        line.strip()
        for line in f.read().split("\n")
        if not line.strip().startswith("#") and not line.strip().startswith("git+")
    ]

extras_require = {}

with open("requirements_test.txt", encoding="utf-8") as f:
    extras_require["test"] = [line.strip() for line in f.read().split("\n") if not line.strip().startswith("#")]

setup(
    name="pyusblamp",
    version=pyusblamp.__version__,
    description="Mailbox Friends Alert (Dream Cheeky) Driver",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=find_packages(),
    install_requires=install_requires,
    extras_require=extras_require,
    include_package_data=(platform == "win32"),
    package_data={
        "libusb": [
            "libusb/MS32/dll/libusb-1.0.dll",
            "libusb/MS32/dll/libusb-1.0.lib",
            "libusb/MS32/dll/libusb-1.0.pdb",
            "libusb/MS64/dll/libusb-1.0.dll",
            "libusb/MS64/dll/libusb-1.0.lib",
            "libusb/MS64/dll/libusb-1.0.pdb",
        ],
    },
    entry_points={
        "console_scripts": [
            "imap2usblamp = pyusblamp:imap2usblamp",
        ],
    },
    author=pyusblamp.__author__,
    author_email="onelife.real@gmail.com",
    license=pyusblamp.__license__,
    license_file="LICENSE",
    url="https://github.com/onelife/PyUsbLamp",
    download_url="https://github.com/onelife/PyUsbLamp/archive/%s.tar.gz" % pyusblamp.__version__,
    keywords=["usblamp", "usb", "lamp", "mailbox", "alert", "driver"],
    classifiers=[
        "Environment :: Console",
        "License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)",
        "Natural Language :: English",
        "Operating System :: Microsoft :: Windows",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 3.10",
        "Topic :: System :: Hardware :: Hardware Drivers",
    ],
)
