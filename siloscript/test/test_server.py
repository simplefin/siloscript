# Copyright (c) The SimpleFIN Team
# See LICENSE for details.

from twisted.trial.unittest import TestCase
from twisted.internet import defer

from mock import MagicMock

from siloscript.storage import MemoryStore
from siloscript.error import InvalidKey
from siloscript.server import Machine, NotFound



class MachineTest(TestCase):

    timeout = 2

    @defer.inlineCallbacks
    def test_basic_functional(self):
        """
        It should work basically like this.
        """        
        store = MemoryStore()
        machine = Machine(
            store=store,
            runner='not real')

        # connect to a channel
        received = []
        def receiver(x):
            received.append(x)

        # create a user-scoped data silo tied to the channel
        silo_key = yield machine.control_makeSilo('jim', 'something',
            channel_receiver=receiver)
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


    def test_run_useScriptRunner(self):
        """
        running a script should be sent to some other script runner rather
        than spawning processes directly with the machine.  It should include
        everything the runner needs to create the DATASTORE_URL.
        """
        # XXX replace this with a better fake
        runner = MagicMock()

        result = defer.Deferred()
        runner.runWithSilo.return_value = result

        store = MemoryStore()
        machine = Machine(
            store=store,
            runner=runner)

        receiver = lambda x: 'foo'

        # start execution
        out_d = machine.run('jim', 'foo.sh', args=['hey'],
            env={'HEY': 'GUYS'},
            channel_receiver=receiver)
        self.assertEqual(out_d.called, False, "Should not have finished yet")

        # while it's still running
        self.assertEqual(runner.runWithSilo.call_count, 1,
            "Should have called runWithSilo")
        args, kwargs = runner.runWithSilo.call_args
        self.assertIn('silo_key', kwargs,
            "Should have given the runner a silo_key")
        self.assertEqual(kwargs['executable'], 'foo.sh')
        self.assertEqual(kwargs['args'], ['hey'])
        self.assertEqual(kwargs['env'], {'HEY': 'GUYS'})
        self.assertIn(kwargs['silo_key'], machine.silos,
            "Should have made a real silo")
        # self.assertEqual(machine.silo_channel[kwargs['silo_key']], ch,
        #     "Silo should be associated with the right channel")

        # finish execution
        result.callback('output')

        self.assertNotIn(kwargs['silo_key'], machine.silos,
            "Should have closed the silo")
        self.assertEqual(self.successResultOf(out_d), 'output',
            "Should return the output of runWithSilo")


    @defer.inlineCallbacks
    def test_run_noChannel(self):
        """
        You don't have to provide a channel to run()
        """
        # XXX replace this with a better fake
        runner = MagicMock()

        runner.runWithSilo.return_value = defer.succeed('hi')

        store = MemoryStore()
        machine = Machine(
            store=store,
            runner=runner)

        # start execution
        out = yield machine.run('jim', 'foo.sh', args=['hey'],
            env={'HEY': 'GUYS'})
        self.assertEqual(out, 'hi')


    @defer.inlineCallbacks
    def test_data_put_keyRestrictions(self):
        """
        Data keys may not start with certain characters.
        """
        machine = Machine(None, None)
        silo_key = machine.control_makeSilo('foo', 'bar')
        yield self.assertFailure(machine.data_put(silo_key, ':key', 'value'),
            InvalidKey)


    @defer.inlineCallbacks
    def test_data_get_keyRestrictions(self):
        """
        Data keys may not start with certain characters.
        """
        machine = Machine(None, None)
        silo_key = machine.control_makeSilo('foo', 'bar')
        yield self.assertFailure(machine.data_get(silo_key, ':key'),
            InvalidKey)


    @defer.inlineCallbacks
    def test_data_get_no_save(self):
        """
        You can get data from a user but not save the data.
        """
        store = MemoryStore()
        machine = Machine(store, None)
        def receiver(question):
            machine.answer_question(question['id'], 'answer')

        silo_key = machine.control_makeSilo('foo', 'bar',
            channel_receiver=receiver)
        value = yield machine.data_get(silo_key,
            'name', prompt='Name?', save=False)
        self.assertEqual(value, 'answer')

        yield self.assertFailure(machine.data_get(silo_key, 'name'),
            KeyError)


    @defer.inlineCallbacks
    def test_data_get_options(self):
        """
        You can provide options.
        """
        store = MemoryStore()
        machine = Machine(store, None)
        def receiver(question):
            self.assertEqual(question['options'], ['1','2','3'])
            machine.answer_question(question['id'], 'answer')

        silo_key = machine.control_makeSilo('foo', 'bar',
            channel_receiver=receiver)
        value = yield machine.data_get(silo_key,
            'name', prompt='Name?', options=['1','2','3'])
        self.assertEqual(value, 'answer')


    @defer.inlineCallbacks
    def test_createToken_unique(self):
        """
        When creating a token, it should be unique.
        """
        machine = Machine(MemoryStore(), None)
        silo_key = machine.control_makeSilo('foo', 'bar')
        t1 = yield machine.data_createToken(silo_key, 'foo')
        t2 = yield machine.data_createToken(silo_key, 'bar')
        self.assertNotEqual(t1, t2, "Should make different tokens"
            " for different values")


    @defer.inlineCallbacks
    def test_data_closeSilo(self):
        """
        You can't do anything to a closed silo.
        """
        machine = Machine(store=MemoryStore(), runner=None)
        silo_key = machine.control_makeSilo('foo', 'bar')
        yield machine.data_put(silo_key, 'foo', 'hi')
        machine.control_closeSilo(silo_key)
        yield self.assertFailure(machine.data_get(silo_key, 'foo'), NotFound)
        yield self.assertFailure(machine.data_put(silo_key, 'a', 'b'), NotFound)
        yield self.assertFailure(machine.data_createToken(silo_key, 'hey'),
            NotFound)


    @defer.inlineCallbacks
    def test_makeSilo_noChannel(self):
        """
        It's okay to make a silo without a channel, but prompts won't work.
        """
        machine = Machine(store=MemoryStore(), runner=None)

        silo_key = machine.control_makeSilo('jim', 'something')

        # there is no one to ask data of
        yield self.assertFailure(machine.data_get(silo_key,
            'something', prompt='Something?'), KeyError)


