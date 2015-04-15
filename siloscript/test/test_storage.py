# Copyright (c) The SimpleFIN Team
# See LICENSE for details.

from twisted.trial.unittest import TestCase
from twisted.internet import defer

from siloscript.storage import Silo, MemoryStore



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
