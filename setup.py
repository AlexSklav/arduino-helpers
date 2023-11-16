#!/usr/bin/env python
# -*- encoding: utf-8 -*-
from setuptools import setup

import versioneer


setup(name='arduino-helpers',
      version=versioneer.get_version(),
      cmdclass=versioneer.get_cmdclass(),
      description='Helper functions for reading configs, etc. from an '
      'installed Arduino directory.',
      author='Christian Fobel',
      author_email='christian@fobel.net',
      url='http://github.com/wheeler-microfluidics/arduino-helpers.git',
      license='GPLv2',
      install_requires=['serial-device', 'path-helpers'],
      packages=['arduino_helpers', 'arduino_helpers.hardware', 'arduino_helpers.bin'],
      include_package_data=True)
