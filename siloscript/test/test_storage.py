# Copyright (c) The SimpleFIN Team
# See LICENSE for details.

from twisted.trial.unittest import TestCase
from twisted.internet import defer
from twisted.python.procutils import which

from mock import MagicMock

import gnupg

from siloscript.storage import Silo, MemoryStore, gnupgWrapper, SQLiteStore
from siloscript.error import CryptError


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
gpg_homedir = None



class gnupgWrapperTest(TestCase, StoreMixin):


    def getEmptyStore(self):
        global gpg_homedir
        if not gpg_homedir:
            gpg_homedir = self.mktemp()
        gpg = gnupg.GPG(homedir=gpg_homedir,
            binary=gpg_bin)
        return gnupgWrapper(gpg, MemoryStore())


class gnupgWrapperTest_with_passphrase(TestCase, StoreMixin):


    def getEmptyStore(self):
        global gpg_homedir
        if not gpg_homedir:
            gpg_homedir = self.mktemp()
        gpg = gnupg.GPG(homedir=gpg_homedir,
            binary=gpg_bin)
        return gnupgWrapper(gpg, MemoryStore(), passphrase='foo')


    @defer.inlineCallbacks
    def test_wrongPassphrase(self):
        """
        If you enter the wrong passphrase, you will get exceptions when
        decrypting.
        """
        tmpdir = self.mktemp()

        mem_store = MemoryStore()

        gpg1 = gnupg.GPG(homedir=tmpdir,
            binary=gpg_bin)
        store1 = gnupgWrapper(gpg1, mem_store, passphrase='foo')

        gpg2 = gnupg.GPG(homedir=tmpdir,
            binary=gpg_bin)
        store2 = gnupgWrapper(gpg2, mem_store, passphrase='not foo')

        yield store1.put('user', 'silo', 'key', 'value')
        yield self.assertFailure(store2.get('user', 'silo', 'key'), CryptError)
        yield store2.put('user', 'silo', 'key2', 'val')
        val = yield store1.get('user', 'silo', 'key2')
        self.assertEqual(val, 'val')



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
        def ask(question):
            called.append(question['prompt'])
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
        def ask(question):
            called.append(question['prompt'])
            return 'answer'
        silo = Silo(store, 'jim', 'africa', ask)

        yield self.assertFailure(silo.get('name'), KeyError)


    @defer.inlineCallbacks
    def test_get_no_save(self):
        """
        You can get data and not save it.
        """
        store = MemoryStore()
        called = []
        def ask(question):
            called.append(question['prompt'])
            return 'answer'
        silo = Silo(store, 'jim', 'africa', ask)
        result = yield silo.get('name', prompt='name?', save=False)
        self.assertEqual(result, 'answer')
        yield self.assertFailure(store.get('jim', 'africa', 'name'),
            KeyError)


    @defer.inlineCallbacks
    def test_get_no_save_no_prompt(self):
        """
        If you don't want to save the data, you must provide a prompt.
        """
        silo = Silo(None, 'jim', 'africa')
        yield self.assertFailure(silo.get('foo', save=False), TypeError)


    @defer.inlineCallbacks
    def test_get_prompt_options(self):
        """
        You can provide a set of options for the prompt.
        """
        store = MemoryStore()
        called = []
        def ask(question):
            called.append(question)
            return 'option1'
        silo = Silo(store, 'jim', 'africa', ask)
        result = yield silo.get('name', prompt='name?', options=[
            'option1', 'option2'])
        self.assertEqual(result, 'option1')
        self.assertEqual(called[0]['options'], ['option1', 'option2'])
        self.assertEqual(called[0]['prompt'], 'name?')


    @defer.inlineCallbacks
    def test_get_CryptError(self):
        """
        If there's a CryptError when getting, raise the error.
        """
        store = MemoryStore()
        store.get = MagicMock()
        store.get.return_value = defer.fail(CryptError())
        
        def ask(question):
            return 'hi'

        silo = Silo(store, 'jim', 'africa', ask)
        yield self.assertFailure(silo.get('name', prompt='name?'), CryptError)

