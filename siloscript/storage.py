# Copyright (c) The SimpleFIN Team
# See LICENSE for details.

from twisted.internet import defer, threads
from twisted.python import log

from siloscript.util import async
from siloscript.error import InvalidKey



class MemoryStore(object):
    """
    I store key-value pairs in memory.
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



class gnupgWrapper(object):
    """
    I wrap a key-value store with encryption.
    """

    def __init__(self, gpg, store, passphrase=None):
        """
        @param gpg: A GPG instance.
        @param store: A data store.
        @param passphrase: Optional passphrase to use for the key.
        """
        self._gpg = gpg
        self._store = store
        self._passphrase = passphrase
        self._sem = defer.DeferredSemaphore(1)


    def _getKey(self):
        """
        Get a key, or wait for the key being generated.
        """
        return self._sem.run(self._actualGetKey)


    @defer.inlineCallbacks
    def _actualGetKey(self):
        """
        Get a key or create one.  Use L{_getKey} rather than me directly.
        """
        private_keys = self._gpg.list_keys(True)
        if not private_keys:
            log.msg("generating key", system='gnupgwrapper')

            kwargs = dict(key_type="RSA", key_length=2048)
            if self._passphrase is not None:
                kwargs['passphrase'] = self._passphrase
            input_data = self._gpg.gen_key_input(**kwargs)
            key = yield threads.deferToThread(self._gpg.gen_key, input_data)
            log.msg("key generated", system='gnupgwrapper')
            private_keys = self._gpg.list_keys(True)

        key = private_keys[0]
        defer.returnValue(key)


    @defer.inlineCallbacks
    def put(self, user, silo, key, value):
        crypto_key = yield self._getKey()
        cipher = yield threads.deferToThread(self._gpg.encrypt,
            value, crypto_key['keyid'], passphrase=self._passphrase)
        result = yield self._store.put(user, silo, key, str(cipher))
        defer.returnValue(result)


    @defer.inlineCallbacks
    def get(self, user, silo, key):
        cipher = yield self._store.get(user, silo, key)
        yield self._getKey()
        plain = yield threads.deferToThread(self._gpg.decrypt, cipher,
            passphrase=self._passphrase)
        defer.returnValue(str(plain))


    def delete(self, user, silo, key):
        return self._store.delete(user, silo, key)



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