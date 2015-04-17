# Copyright (c) The SimpleFIN Team
# See LICENSE for details.

from twisted.internet import defer

from functools import wraps

def async(f):
    @wraps(f)
    def deco(*args, **kwargs):
        return defer.maybeDeferred(f, *args, **kwargs)
    return deco


class MemoryStore(object):
    """
    XXX
    """

    def __init__(self):
        self._data = {}

    @async
    def get(self, user, silo, key):
        return self._data[(user, silo, key)]

    @async
    def put(self, user, silo, key, value):
        self._data[(user, silo, key)] = value

    @async
    def delete(self, user, silo, key):
        self._data.pop((user, silo, key))



class Silo(object):
    """
    I provide access to a restricted set of data in a key-value store.
    """

    def __init__(self, store, user, silo, prompt_func=None):
        """
        @param store: A key-value store with get/put methods.
            See L{MemoryStore}
        @param user: A string user identifier.
        @param silo: A string silo identifier.
        @param prompt_func: A function that will be called with prompts when
            data is not available in the store.
        """
        self.store = store
        self.user = user
        self.silo = silo
        self.prompt_func = prompt_func


    def get(self, key, prompt=None):
        """
        Get a value from the silo.
        """
        d = self.store.get(self.user, self.silo, key)
        if self.prompt_func and prompt:
            d.addErrback(self._promptAndSave, key, prompt)
        return d


    def _promptAndSave(self, err, key, prompt):
        """
        Prompt the user for the value.
        """
        d = defer.maybeDeferred(self.prompt_func, prompt)
        d.addCallback(self._save, key)
        return d


    def _save(self, value, key):
        d = self.put(key, value)
        d.addCallback(lambda _: value)
        return d


    def put(self, key, value):
        """
        Set a value within the silo.
        """
        return self.store.put(self.user, self.silo, key, value)