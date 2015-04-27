# Copyright (c) The SimpleFIN Team
# See LICENSE for details.

class Error(Exception): pass
class NotFound(Error): pass
class InvalidKey(Error): pass
class CryptError(Error): pass
