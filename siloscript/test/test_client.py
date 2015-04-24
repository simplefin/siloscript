# Copyright (c) The SimpleFIN Team
# See LICENSE for details.
from twisted.trial.unittest import TestCase
from twisted.internet import reactor, endpoints, defer, threads
from twisted.web.server import Site
from twisted.python import log

from siloscript.storage import MemoryStore
from siloscript.server import Machine, DataWebApp
from siloscript.client import Client
from siloscript.error import NotFound



class Functional_ClientTest(TestCase):

    timeout = 5

    @defer.inlineCallbacks
    def startServer(self, answers=None, open_channel=True):
        """
        Start a server.
        """
        answers = answers or {}

        # start a server
        self.store = MemoryStore()
        machine = Machine(self.store, None)
        data_app = DataWebApp(machine)
        ep = endpoints.serverFromString(reactor, 'tcp:0:interface=127.0.0.1')
        p = yield ep.listen(Site(data_app.app.resource()))
        self.addCleanup(p.stopListening)
        host = p.getHost()
        url = 'http://%s:%s' % (host.host, host.port)

        channel_key = None
        if open_channel:
            # open a channel for user interaction
            channel_key = machine.channel_open()
            def receiver(question):
                answer = answers.get(question['prompt'])
                machine.answer_question(question['id'], answer)
            machine.channel_connect(channel_key, receiver)

        # make a silo
        silo_key = machine.control_makeSilo('foo', 'bar', channel_key)
        url = '%s/%s' % (url, silo_key)
        log.msg('url: %r' % (url,))
        defer.returnValue(url)


    @defer.inlineCallbacks
    def test_getValue_prompt_withUserInteraction(self):
        """
        You should be able to get a value from a data server.
        """
        url = yield self.startServer(answers={
            'Account ID?': '12345',
        })

        # make client
        client = Client(url)
        result = yield threads.deferToThread(client.getValue,
            'account_id',
            prompt='Account ID?')
        self.assertEqual(result, '12345')


    @defer.inlineCallbacks
    def test_getValue_prompt_noSave(self):
        """
        You can get a value and not save it.
        """
        url = yield self.startServer(answers={
            'Account ID?': '12345',
        })

        # make client
        client = Client(url)
        result = yield threads.deferToThread(client.getValue,
            'account_id',
            prompt='Account ID?',
            save=False)
        self.assertEqual(result, '12345')

        yield self.assertFailure(threads.deferToThread(client.getValue,
            'account_id'), NotFound)


    @defer.inlineCallbacks
    def test_getValue_prompt_noUserInteraction(self):
        """
        It is an error to prompt for a value when there's no channel
        to ask questions of.
        """
        url = yield self.startServer(open_channel=False)

        client = Client(url)
        yield self.assertFailure(threads.deferToThread(client.getValue,
            'account_id',
            prompt='Account ID?'), NotFound)


    @defer.inlineCallbacks
    def test_getValue_noPrompt(self):
        """
        You don't have to prompt.
        """
        url = yield self.startServer(open_channel=False)

        client = Client(url)
        yield self.assertFailure(threads.deferToThread(client.getValue,
            'account_id'), NotFound)


    @defer.inlineCallbacks
    def test_getValue_options(self):
        """
        You can provide a list of acceptable options.
        """
        url = yield self.startServer(answers={
            'Color?': 'yellow',
        })

        # make client
        client = Client(url)
        result = yield threads.deferToThread(client.getValue,
            'color',
            prompt='Color?',
            options=['yellow', 'orange', 'blue'])
        self.assertEqual(result, 'yellow')


    @defer.inlineCallbacks
    def test_getValue_options_nonOptionOkay(self):
        """
        You might get back an answer that wasn't one of the options.  You
        should check this on your own if you care.
        """
        url = yield self.startServer(answers={
            'Color?': 'purple',
        })

        # make client
        client = Client(url)
        result = yield threads.deferToThread(client.getValue,
            'color',
            prompt='Color?',
            options=['yellow', 'orange', 'blue'])
        self.assertEqual(result, 'purple', "Even though it wasn't an option"
            " it can be returned.")


    @defer.inlineCallbacks
    def test_putValue(self):
        """
        You can save values.
        """
        url = yield self.startServer(open_channel=False)

        client = Client(url)
        yield threads.deferToThread(client.putValue, 'foo', 'bar')
        result = yield threads.deferToThread(client.getValue, 'foo')
        self.assertEqual(result, 'bar')


    @defer.inlineCallbacks
    def test_putValue_badURL(self):
        """
        It will fail if you try to putValue on a bad url.
        """
        url = yield self.startServer(open_channel=False)

        client = Client(url + 'fake')
        yield self.assertFailure(threads.deferToThread(
            client.putValue, 'foo', 'bar'), NotFound)


    @defer.inlineCallbacks
    def test_getToken(self):
        """
        You can get tokens for things.
        """
        url = yield self.startServer(open_channel=False)

        client = Client(url)
        token = yield threads.deferToThread(client.getToken, 'hey')
        self.assertNotEqual(token, 'hey')
        t2 = yield threads.deferToThread(client.getToken, 'hey')
        self.assertEqual(token, t2, "Should return the same token"
            " for the same value")
        t3 = yield threads.deferToThread(client.getToken, 'guys')
        self.assertNotEqual(t2, t3,
            "Should return a new token for a new value")


    @defer.inlineCallbacks
    def test_getToken_badRequest(self):
        """
        It will fail if something is wrong with the request.
        """
        url = yield self.startServer(open_channel=False)

        client = Client(url + 'fake')
        yield self.assertFailure(threads.deferToThread(
            client.getToken, 'foo'), NotFound)










