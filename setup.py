from setuptools import setup
from sys import platform
import pyusblamp

setup(
    name='pyusblamp',
    packages=['pyusblamp'],
    version=pyusblamp.__version__,
    description='Mailbox Friends Alert (Dream Cheeky) Driver',
    license='GPLv3',
    install_requires=['six', 'pyusb', ],

    author='onelife',
    author_email='onelife.real[AT]gmail.com',

    url='https://github.com/onelife/PyUsbLamp',
    download_url='https://github.com/onelife/PyUsbLamp/archive/%s.tar.gz' % pyusblamp.__version__,

    keywords=['usblamp', 'usb', 'lamp', 'mailbox', 'alert', 'driver'],
    classifiers=[
        'Environment :: Console',
        'License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)',
        'Natural Language :: English',
        'Operating System :: Microsoft :: Windows',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.6',
        'Topic :: System :: Hardware :: Hardware Drivers',
    ],

    include_package_data=(platform == 'win32'),
    package_data={
        'libusb': [
            'libusb/MS32/dll/libusb-1.0.dll',
            'libusb/MS32/dll/libusb-1.0.lib',
            'libusb/MS32/dll/libusb-1.0.pdb',
            'libusb/MS64/dll/libusb-1.0.dll',
            'libusb/MS64/dll/libusb-1.0.lib',
            'libusb/MS64/dll/libusb-1.0.pdb',
        ],
    },

    entry_points={
        'console_scripts': [
            'imap2usblamp = pyusblamp:imap2usblamp',
        ],
    }
)
