# Copyright (c) The SimpleFIN Team
# See LICENSE for details.

from twisted.trial.unittest import TestCase


from siloscript.storage import MemoryStore
from siloscript.channel import Station



class StationTest(TestCase):


    def test_init(self):
        """
        A station has a data store.
        """
        store = MemoryStore()
        s = Station(store)
        self.assertEqual(s.store, store)


    def test_basicChannelUse(self):
        """
        You can use channels.
        """
        s = Station(MemoryStore())
        
        called = []
        def func(prompt):
            called.append(prompt)
            return 'answer'
        
        ch = s.createChannel(func)
        self.assertEqual(type(ch), str)
        result = s.askQuestion(ch, 'How old are you?')
        self.assertEqual(called, ['How old are you?'])
        self.assertEqual(self.successResultOf(result), 'answer')
