# Copyright (c) The SimpleFIN Team
# See LICENSE for details.

from twisted.trial.unittest import TestCase
from twisted.internet import defer
from twisted.python.filepath import FilePath


from siloscript.storage import MemoryStore
from siloscript.server import TokenInternals


class TokenInternalsTest(TestCase):


    @defer.inlineCallbacks
    def test_basic_functional(self):
        """
        It should work basically like this.
        """        
        store = MemoryStore()
        machine = TokenInternals(
            store=store,
            script_root='not real')

        # create a channel
        channel_key = yield machine.channel_open()
        self.assertIsInstance(channel_key, str)

        # connect to a channel
        received = []
        def receiver(x):
            received.append(x)
        machine.channel_connect(channel_key, receiver)

        # wait for channel close
        ch_close = machine.channel_notifyClosed(channel_key)
        self.assertEqual(ch_close.called, False, "Should not be done yet")

        # create a user-scoped data silo tied to the channel
        silo_key = yield machine.control_makeSilo('jim', 'something',
            channel_key)
        self.assertIsInstance(silo_key, str)

        # ask for data
        response_d = machine.data_get(silo_key, 'something', prompt='Something?')
        self.assertEqual(len(received), 1, "Should have asked the channel")
        question = received[0]
        self.assertEqual(question['prompt'], 'Something?')
        self.assertNotEqual(question['id'], None, "Should have a question ID")

        # respond with an answer
        machine.answer_question(question['id'], 'Nothing')
        response = yield response_d
        self.assertEqual(response, 'Nothing')

        # save some data and get it out
        yield machine.data_put(silo_key, 'hey', 'HEY')
        result = yield machine.data_get(silo_key, 'hey')
        self.assertEqual(result, 'HEY', "Should return stored value")

        # create an opaque token
        token1 = yield machine.data_createToken(silo_key, 'guys')
        self.assertIsInstance(token1, str)
        self.assertNotEqual(token1, 'guys')
        token2 = yield machine.data_createToken(silo_key, 'guys')
        self.assertEqual(token1, token2)

        # ask for data without prompting
        response = yield machine.data_get(silo_key, 'hey')
        self.assertEqual(response, 'HEY')

        # close the silo, which will close the channel
        yield machine.control_closeSilo(silo_key)

        self.assertEqual(self.successResultOf(ch_close), channel_key,
            "The channel should have been closed")


    @defer.inlineCallbacks
    def test_run_basic_noChannel(self):
        """
        A basic run looks like this.
        """
        script_root = FilePath(self.mktemp())
        script_root.makedirs()
        foo_script = script_root.child('foo.sh')
        foo_script.setContent('#!/bin/bash\necho hey from foo')
        store = MemoryStore()
        machine = TokenInternals(
            store=store,
            script_root=script_root.path)
        out, err, rc = yield machine.run_runScript('jim', 'foo.sh', args=[])
        self.assertEqual(out, 'hey from foo\n')
        self.assertEqual(err, '')
        self.assertEqual(rc, 0)


    def test_run_useScriptRunner(self):
        """
        running a script should be sent to some other script runner rather
        than spawning processes directly with the machine.  It should include
        everything the runner needs to create the DATASTORE_URL.
        """
        self.fail('write me')


    def test_channel_closed(self):
        """
        You can't connect to a closed channel.  A notifyClosed on a closed
        channel will fire immediately.
        """
        self.fail('write me')


    def test_run_notExecutable(self):
        """
        Only user-executable scripts can be run.
        """
        self.fail('write me')


    def test_channel_connect_withPendingQuestions(self):
        """
        Deliver all pending question to channels when they connect.
        """
        self.fail('write me')


    def test_data_put_keyRestrictions(self):
        """
        Data keys may not start with certain characters.
        """
        self.fail('write me')


    def test_data_get_keyRestrictions(self):
        """
        Data keys may not start with certain characters.
        """
        self.fail('write me')


    def test_data_closeSilo(self):
        """
        You can't do anything to a closed silo.
        """
        self.fail('write me')


    def test_closeSilo_channelClosed(self):
        """
        If the channel is already closed, closing the associated silo should
        not be an error.
        """
        self.fail('write me')


    def test_makeSilo_timeout(self):
        """
        Silos should not exist forever.
        """



