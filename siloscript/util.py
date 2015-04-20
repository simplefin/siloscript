# Copyright (c) The SimpleFIN Team
# See LICENSE for details.

from twisted.internet import defer
from functools import wraps

def async(f):
    @wraps(f)
    def deco(*args, **kwargs):
        return defer.maybeDeferred(f, *args, **kwargs)
    return deco
