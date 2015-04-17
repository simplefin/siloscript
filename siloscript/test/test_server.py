# Copyright (c) The SimpleFIN Team
# See LICENSE for details.

from twisted.trial.unittest import TestCase
from twisted.internet import defer

from mock import MagicMock

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
            runner='not real')

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


    def test_run_useScriptRunner(self):
        """
        running a script should be sent to some other script runner rather
        than spawning processes directly with the machine.  It should include
        everything the runner needs to create the DATASTORE_URL.
        """
        # XXX replace this with a better fake
        runner = MagicMock()

        result = defer.Deferred()
        runner.runScript.return_value = result

        store = MemoryStore()
        machine = TokenInternals(
            store=store,
            runner=runner)

        ch = machine.channel_open()

        # start execution
        out_d = machine.run('jim', 'foo.sh', args=['hey'],
            channel_key=ch)
        self.assertEqual(out_d.called, False, "Should not have finished yet")

        # while it's still running
        self.assertEqual(runner.runScript.call_count, 1,
            "Should have called runScript")
        args, kwargs = runner.runScript.call_args
        self.assertIn('silo_key', kwargs,
            "Should have given the runner a silo_key")
        self.assertEqual(kwargs['script'], 'foo.sh')
        self.assertEqual(kwargs['args'], ['hey'])
        self.assertIn(kwargs['silo_key'], machine.silos,
            "Should have made a real silo")
        self.assertEqual(machine.silo_channel[kwargs['silo_key']], ch,
            "Silo should be associated with the right channel")

        # finish execution
        result.callback('output')

        self.assertNotIn(kwargs['silo_key'], machine.silos,
            "Should have closed the silo")
        self.assertEqual(self.successResultOf(out_d), 'output',
            "Should return the output of runScript")


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


    def test_run_noChannel(self):
        """
        You don't have to provide a channel to run()
        """
        self.fail('write me')


    def test_channel_connect_withPendingQuestions(self):
        """
        Deliver all pending question to channels when they connect.
        """
        self.fail('write me')


    def test_channel_connect_noSuchChannel(self):
        """
        You can't connect to a channel that doesn't exist.
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
        self.fail('write me')


    def test_makeSilo_nonExistingChannel(self):
        """
        It is an error to make a silo attached to a channel that doesn't exist.
        """
        self.fail('write me')



