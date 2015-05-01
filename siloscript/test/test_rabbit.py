# Copyright (c) The SimpleFIN Team
# See LICENSE for details.

from twisted.trial.unittest import TestCase

from twisted.internet import defer

from mock import MagicMock

from siloscript.storage import MemoryStore
from siloscript.server import Machine
from siloscript.rabbit import RabbitMachine, makeConnection, RabbitClient

import os


skip_rabbit = 'You must provide a RABBITMQ_URL to run these tests.'
if 'RABBITMQ_URL' in os.environ:
    skip_rabbit = ''



class RabbitClientTest(TestCase):

    skip = skip_rabbit


class RabbitMachineTest(TestCase):

    timeout = 2
    skip = skip_rabbit

    def setUp(self):
        self.url = os.environ['RABBITMQ_URL']


    @defer.inlineCallbacks
    def conn(self):
        conn = yield makeConnection(self.url)

        @defer.inlineCallbacks
        def cleanup(conn):
            if conn.heartbeat:
                conn.heartbeat.stop()
            yield conn.close()
            yield conn.transport.loseConnection()
        self.addCleanup(cleanup, conn)
        defer.returnValue(conn)


    @defer.inlineCallbacks
    def test_runScript_noChannel(self):
        """
        You should be able to run a script with no input channel.
        """
        runner = MagicMock()
        runner.runWithSilo.return_value = defer.succeed('hi')
        
        store = MemoryStore()
        machine = Machine(store=store, runner=runner)
        server_conn = yield self.conn()
        rab = RabbitMachine(machine, server_conn)
        rab.start()
        self.addCleanup(rab.stop)

        client_conn = yield self.conn()
        client = RabbitClient(client_conn)

        result_d = defer.Deferred()
        yield client.subscribeToResults(result_d.callback)
        self.addCleanup(client.stop)

        yield client.run('jim', 'script', ['arg'],
            {'FOO': 'BAR'})

        result = yield result_d

        self.assertEqual(runner.runWithSilo.call_count, 1,
            "Should have called machine.runWithSilo")
        args, kwargs = runner.runWithSilo.call_args
        self.assertIn('silo_key', kwargs)
        self.assertEqual(kwargs['executable'], 'script')
        self.assertEqual(kwargs['args'], ['arg'])
        self.assertEqual(kwargs['env'], {'FOO': 'BAR'})

        self.assertEqual(result['msg']['user'], 'jim')
        self.assertEqual(result['msg']['executable'], 'script')
        self.assertEqual(result['msg']['args'], ['arg'])
        self.assertEqual(result['msg']['env'], {'FOO': 'BAR'})
        self.assertEqual(result['result'], 'hi')


    @defer.inlineCallbacks
    def test_runScript_channel(self):
        """
        You can run a script with an input channel.  Prompts will be sent
        over Rabbit, but answers are sent to the machine (over HTTP in a
        normal deployment)
        """
        runner = MagicMock()

        @defer.inlineCallbacks
        def runWithSilo(silo_key, *args, **kwargs):
            answer = yield machine.data_get(silo_key, 'something',
                prompt='Something?')
            defer.returnValue('answer: %s' % (answer,))
        runner.runWithSilo.side_effect = runWithSilo
        
        store = MemoryStore()
        machine = Machine(store=store, runner=runner)
        server_conn = yield self.conn()
        rab = RabbitMachine(machine, server_conn)
        rab.start()
        self.addCleanup(rab.stop)

        client_conn = yield self.conn()
        client = RabbitClient(client_conn)

        result_d = defer.Deferred()
        yield client.subscribeToResults(result_d.callback)
        self.addCleanup(client.stop)

        questions = []
        def questionReceiver(question):
            questions.append(question)
            machine.answer_question(question['id'], 'the answer')

        yield client.run('jim', 'script', ['arg'],
            {'FOO': 'BAR'}, question_receiver=questionReceiver)

        result = yield result_d
        self.assertEqual(result['result'], 'answer: the answer')
        
        self.assertEqual(len(questions), 1, "Should have asked one question "
            "over the channel")
        question = questions[0]
        self.assertEqual(question['prompt'], 'Something?')


    @defer.inlineCallbacks
    def test_run_return_result(self):
        """
        You can get the answer to the run, if you want.
        """
        runner = MagicMock()
        runner.runWithSilo.return_value = defer.succeed('hi')
        
        store = MemoryStore()
        machine = Machine(store=store, runner=runner)
        server_conn = yield self.conn()
        rab = RabbitMachine(machine, server_conn)
        rab.start()
        self.addCleanup(rab.stop)

        client_conn = yield self.conn()
        client = RabbitClient(client_conn)
        self.addCleanup(client.stop)

        result = yield client.run('jim', 'script', ['arg'],
            {'FOO': 'BAR'}, return_result=True)

        self.assertEqual(result['msg']['user'], 'jim')
        self.assertEqual(result['msg']['executable'], 'script')
        self.assertEqual(result['msg']['args'], ['arg'])
        self.assertEqual(result['msg']['env'], {'FOO': 'BAR'})
        self.assertEqual(result['result'], 'hi')


