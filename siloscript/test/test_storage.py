# Copyright (c) The SimpleFIN Team
# See LICENSE for details.

from twisted.trial.unittest import TestCase
from twisted.internet import defer
from twisted.python.procutils import which

import gnupg

from siloscript.storage import Silo, MemoryStore, gnupgWrapper, SQLiteStore


class StoreMixin(object):


    def getEmptyStore(self):
        raise NotImplementedError("You must implement getEmptyStore")


    @defer.inlineCallbacks
    def test_basic(self):
        """
        You should be able to set and get stuff.
        """
        store = yield self.getEmptyStore()
        yield store.put('jim', 'silo1', 'foo', 'FOO')
        val = yield store.get('jim', 'silo1', 'foo')
        self.assertEqual(val, 'FOO')


    @defer.inlineCallbacks
    def test_binary(self):
        """
        Binary data should be okay.
        """
        store = yield self.getEmptyStore()
        yield store.put('a', 'b', 'c', '\x00\x01')
        val = yield store.get('a', 'b', 'c')
        self.assertEqual(val, '\x00\x01')

    
    @defer.inlineCallbacks
    def test_get_user_KeyError(self):
        """
        If the user key doesn't exist, it should return a key error.
        """
        store = yield self.getEmptyStore()
        yield store.put('jim', 'silo1', 'foo', 'FOO')
        yield self.assertFailure(store.get('notjim', 'silo1', 'foo'), KeyError)


    @defer.inlineCallbacks
    def test_get_silo_KeyError(self):
        """
        If the silo key doesn't exist, it should return a key error.
        """
        store = yield self.getEmptyStore()
        yield store.put('jim', 'silo1', 'foo', 'FOO')
        yield self.assertFailure(store.get('jim', 'silo2', 'foo'), KeyError)


    @defer.inlineCallbacks
    def test_get_key_KeyError(self):
        """
        If the key doesn't exist, it should return a key error.
        """
        store = yield self.getEmptyStore()
        yield store.put('jim', 'silo1', 'foo', 'FOO')
        yield self.assertFailure(store.get('jim', 'silo1', 'foom'), KeyError)


    @defer.inlineCallbacks
    def test_delete(self):
        """
        You can delete keys.
        """
        store = yield self.getEmptyStore()
        yield store.put('jim', 'silo1', 'foo', 'FOO')
        yield store.delete('jim', 'silo1', 'foo')
        yield self.assertFailure(store.get('jim', 'silo1', 'foo'), KeyError)


    @defer.inlineCallbacks
    def test_delete_KeyError(self):
        """
        You can't delete keys that aren't there.
        """
        store = yield self.getEmptyStore()
        yield self.assertFailure(store.delete('jim', 'silo1', 'foo'), KeyError)



class MemoryStoreTest(TestCase, StoreMixin):


    def getEmptyStore(self):
        return MemoryStore()



class SQLiteStoreTest(TestCase, StoreMixin):


    def getEmptyStore(self):
        return SQLiteStore.create(':memory:')



gpg_bin = which('gpg')[0]



class gnupgWrapperTest(TestCase, StoreMixin):


    def getEmptyStore(self):
        tmpdir = self.mktemp()
        gpg = gnupg.GPG(homedir=tmpdir,
            binary=gpg_bin)
        return gnupgWrapper(gpg, MemoryStore())


class gnupgWrapperTest_with_passphrase(TestCase, StoreMixin):


    def getEmptyStore(self):
        tmpdir = self.mktemp()
        gpg = gnupg.GPG(homedir=tmpdir,
            binary=gpg_bin)
        return gnupgWrapper(gpg, MemoryStore(), passphrase='foo')


class SiloTest(TestCase):


    @defer.inlineCallbacks
    def test_noUser_basic(self):
        """
        A silo without a user just wraps the storage.
        """
        store = MemoryStore()
        silo = Silo(store, 'user', 'africa')
        yield silo.put('foo', 'bar')
        result = yield silo.get('foo')
        self.assertEqual(result, 'bar', "Should store foo")
        result = yield store.get('user', 'africa', 'foo')
        self.assertEqual(result, 'bar', "Should store under user/africa")


    @defer.inlineCallbacks
    def test_noUser_getNotThere(self):
        """
        If the value is not set, it should be a KeyError.
        """
        store = MemoryStore()
        silo = Silo(store, 'user', 'africa')
        yield self.assertFailure(silo.get('hey'), KeyError)


    @defer.inlineCallbacks
    def test_noUser_prompt(self):
        """
        If the value is not set, and there's no user, it should
        be a KeyError even if you prompt.
        """
        store = MemoryStore()
        silo = Silo(store, 'user', 'africa')
        yield self.assertFailure(silo.get('hey', prompt='Hey?'),
            KeyError)


    @defer.inlineCallbacks
    def test_user_basic(self):
        """
        A silo with a user can ask the user for more information.
        """
        store = MemoryStore()
        called = []
        def ask(prompt):
            called.append(prompt)
            return 'answer'
        silo = Silo(store, 'jim', 'africa', ask)

        result = yield silo.get('name', prompt='name?')

        self.assertEqual(called, ['name?'],
            "Should have asked the user.")
        self.assertEqual(result, 'answer')

        called.pop()
        cached = yield silo.get('name', prompt='name?')
        self.assertEqual(called, [], "Should not have asked the user because "
            "the value was cached.")
        self.assertEqual(cached, 'answer')


    @defer.inlineCallbacks
    def test_user_noprompt(self):
        """
        If there's a function available to prompt, but no prompt is given,
        don't ask the user.
        """
        store = MemoryStore()
        called = []
        def ask(prompt):
            called.append(prompt)
            return 'answer'
        silo = Silo(store, 'jim', 'africa', ask)

        yield self.assertFailure(silo.get('name'), KeyError)
