# Copyright (c) The SimpleFIN Team
# See LICENSE for details.

from setuptools import setup, find_packages

import re
import os

def getVersion():
    """
    Get version from version file without importing.
    """
    r = re.compile(r'__version__ = "(.*?)"')
    version_file = os.path.join(os.path.dirname(__file__), 'siloscript/version.py')
    fh = open(version_file, 'rb')
    for line in fh.readlines():
        m = r.match(line)
        if m:
            return m.groups()[0]


setup(
    url='https://github.com/simplefin/siloscript',
    author='SimpleFIN Team',
    author_email='matt@simplefin.org',
    name='siloscript',
    version=getVersion(),
    include_package_data=True,
    packages=find_packages(),
    install_requires=[
        'klein>=15.0.0',
        'gnupg',
        'pysqlite',
    ],
    scripts=[
        'bin/siloscript',
    ],
)

