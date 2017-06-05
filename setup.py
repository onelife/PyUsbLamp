from setuptools import setup

setup(
   name = 'pyusblamp',
   packages = ['pyusblamp'],
   version = '0.15',
   description = 'Mailbox Friends Alert (Dream Cheeky) Driver',
   license='GPLv3',
   install_requires=['pyusb',],
   
   author = 'onelife',
   author_email = 'onelife.real[AT]gmail.com',
   
   url = 'https://github.com/onelife/PyUsbLamp',
   download_url = 'https://github.com/onelife/PyUsbLamp/archive/0.1.tar.gz',
   
   keywords = ['usblamp', 'usb', 'lamp', 'mailbox', 'alert', 'driver'],
   classifiers = [
      'Environment :: Win32 (MS Windows)',
      'License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)',
      'Natural Language :: English',
      'Operating System :: Microsoft :: Windows',
      'Programming Language :: Python :: 2.7',
      'Topic :: System :: Hardware :: Hardware Drivers',
   ],
   
   include_package_data = True,
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
         'pyusblamp = pyusblamp:main',
      ],
   }
)