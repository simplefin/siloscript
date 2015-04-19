# Copyright (c) The SimpleFIN Team
# See LICENSE for details.

from twisted.internet import defer
from klein import Klein
from twisted.python import log
from twisted.python.filepath import FilePath
from twisted.web.static import File

import hashlib
import sys

import json
from functools import partial, wraps
from collections import defaultdict
from uuid import uuid4

from siloscript.storage import MemoryStore, Silo, InvalidKey
from siloscript.util import async
from siloscript.error import NotFound



class Machine(object):
    """
    XXX
    """

    invalid_key_prefix = ':'
    token_prefix = ':private:'
    token_salt = 'dssdfh09w83hof08hasodifaosdnfsadf'


    def __init__(self, store, runner):
        self.store = store
        self.runner = runner

        self.channels = set()
        self.receivers = defaultdict(list)
        self.silos = {}
        self.silo_channel = {}
        self.pending_questions_by_id = {}
        self.pending_channelClosed_notifications = defaultdict(list)
        self.pending_questions_by_channel = defaultdict(list)


    def channel_open(self):
        """
        XXX
        """
        key = 'CH-%s' % (uuid4(),)
        self.channels.add(key)
        return key


    def channel_connect(self, channel_key, receiver):
        """
        XXX
        """
        if channel_key not in self.channels:
            raise KeyError("No such channel")
        self.receivers[channel_key].append(receiver)
        for question in list(self.pending_questions_by_channel[channel_key]):
            receiver(question['data'])


    def channel_disconnect(self, channel_key, receiver):
        """
        XXX
        """
        self.receivers[channel_key].remove(receiver)


    def channel_notifyClosed(self, channel_key):
        """
        XXX
        """
        if channel_key not in self.channels:
            return defer.succeed(None)
        d = defer.Deferred()
        self.pending_channelClosed_notifications[channel_key].append(d)
        return d


    def channel_close(self, channel_key):
        """
        XXX
        """
        if channel_key in self.channels:
            self.channels.remove(channel_key)
        for d in self.pending_channelClosed_notifications[channel_key]:
            d.callback(channel_key)


    def channel_prompt(self, channel_key, prompt):
        """
        XXX
        """
        question_id = 'Q-%s' % (uuid4(),)
        
        answer_d = defer.Deferred()
        question = {
            'channel_key': channel_key,
            'd': answer_d,
            'data': {
                'id': question_id,
                'prompt': prompt,
            },
        }
        self.pending_questions_by_id[question_id] = question
        self.pending_questions_by_channel[channel_key].append(question)

        for receiver in self.receivers[channel_key]:
            receiver(question['data'])

        return answer_d


    def answer_question(self, question_id, answer):
        """
        XXX
        """
        question = self.pending_questions_by_id.pop(question_id)
        self.pending_questions_by_channel[question['channel_key']]\
            .remove(question)
        question['d'].callback(answer)



    def control_makeSilo(self, user, subkey, channel_key=None):
        """
        XXX
        """
        func = None
        if channel_key:
            if channel_key not in self.channels:
                raise KeyError("No such channel: %r" % (channel_key,))
            func = partial(self.channel_prompt, channel_key)
        silo = Silo(self.store, user, subkey, func)
        key = 'SILO-%s' % (uuid4(),)
        self.silos[key] = silo
        self.silo_channel[key] = channel_key
        return key


    def control_closeSilo(self, silo_key):
        """
        XXX
        """
        self.silos.pop(silo_key)
        channel_key = self.silo_channel.pop(silo_key)
        self.channel_close(channel_key)


    def run(self, user, executable, args, env, channel_key=None):
        """
        XXX
        """
        silo_key = self.control_makeSilo(user, executable, channel_key)
        def cleanup(result):
            self.control_closeSilo(silo_key)
            return result
        d = self.runner.runWithSilo(
            silo_key=silo_key,
            executable=executable,
            args=args,
            env=env)
        d.addBoth(cleanup)
        return d


    def _data_validateUserSuppliedKey(self, key):
        """
        XXX
        """
        if key.startswith(self.invalid_key_prefix):
            raise InvalidKey('Invalid key: %r' % (key,))


    @async
    def data_get(self, silo_key, key, prompt=None):
        """
        XXX
        """
        if silo_key not in self.silos:
            raise NotFound(silo_key)
        self._data_validateUserSuppliedKey(key)
        return self.silos[silo_key].get(key, prompt)


    @async
    def data_put(self, silo_key, key, value):
        """
        XXX
        """
        if silo_key not in self.silos:
            raise NotFound(silo_key)
        self._data_validateUserSuppliedKey(key)
        return self.silos[silo_key].put(key, value)


    @defer.inlineCallbacks
    def data_createToken(self, silo_key, value):
        """
        XXX
        """
        if silo_key not in self.silos:
            raise NotFound(silo_key)
        silo = self.silos[silo_key]
        h = hashlib.sha1(value + self.token_salt).hexdigest()
        key = self.token_prefix + h
        try:
            opaque = yield silo.get(key)
        except KeyError:
            opaque = 'TK-%s' % (uuid4(),)
            yield silo.put(key, opaque)
        defer.returnValue(opaque)





def sseMsg(name, data):
    return 'event: %s\ndata: %s\n\n' % (name, json.dumps(data))



def cors(f):
    """
    Decorate a handler to support CORS.
    """
    @wraps(f)
    def deco(instance, request, *args, **kwargs):
        request.setHeader('Access-Control-Allow-Origin', '*')
        return f(instance, request, *args, **kwargs)
    return deco



class PublicWebApp(object):

    app = Klein()

    def __init__(self, machine):
        self.machine = machine


    @app.route('/answer/<string:question_id>', methods=['POST', 'OPTIONS'])
    @cors
    def answer_question(self, request, question_id):
        """
        Answer a question posed to a user.
        """
        if request.method == 'OPTIONS':
            return
        answer = request.content.read()
        self.machine.answer_question(question_id, answer)



class ControlWebApp(object):

    app = Klein()

    def __init__(self, machine, static_root):
        self.machine = machine
        self.static_root = static_root


    @app.route('/static', methods=['GET'], branch=True)
    def static(self, request):
        return File(self.static_root)


    @app.route('/channel/open', methods=['GET'])
    def channel_open(self, request):
        """
        Create a new channel for a user to receive questions.
        """
        return self.machine.channel_open()


    @app.route('/channel/<string:channel_key>/events', methods=['GET'])
    def channel_events(self, request, channel_key):
        request.setHeader('Content-type', 'text/event-stream')
        request.write(sseMsg('channel_key', channel_key))

        def receiver(request, data):
            request.write(sseMsg('question', {
                'id': data['id'],
                'prompt': data['prompt'],
            }))

        self.machine.channel_connect(channel_key, partial(receiver, request))
        
        # XXX need to add disconnect checking
        # request.notifyFinish().addCallback(rm, channel_key)
        return defer.Deferred()

    @app.route('/run/<string:user>', methods=['POST'])
    def run(self, request, user):
        """
        Run a script for a user.
        """
        script = request.args.get('script', [None])[0]
        channel_key = request.args.get('channel_key', [None])[0]
        args = json.loads(request.args.get('args', ["[]"])[0])

        d = self.machine.run(user, script, args, {}, channel_key)
        # just return output
        # XXX change this later to look at exit code
        d.addCallback(lambda x: x[0])
        return d



class DataWebApp(object):

    app = Klein()

    def __init__(self, machine):
        self.machine = machine


    @app.route('/<string:silo_key>/<string:key>', methods=['GET'])
    @defer.inlineCallbacks
    def data_GET(self, request, silo_key, key):
        prompt = request.args.get('prompt', [None])[0]
        try:
            value = yield self.machine.data_get(silo_key, key, prompt)
            defer.returnValue(value)
        except KeyError:
            request.setResponseCode(404)


    @app.route('/<string:silo_key>/<string:key>', methods=['PUT'])
    def data_PUT(self, request, silo_key, key):
        value = request.content.read()
        try:
            return self.machine.data_put(silo_key, key, value)
        except KeyError:
            request.setResponseCode(404)


    @app.route('/<string:silo_key>', methods=['POST'])
    @defer.inlineCallbacks
    def data_getID(self, request, silo_key):
        value = request.args.get('value', [''])[0]
        try:
            value = yield self.machine.data_createToken(silo_key, value)
            defer.returnValue(value)
        except KeyError:
            request.setResponseCode(404)




class UIServer(object):

    app = Klein()

    my_root = 'http://127.0.0.1:9600'

    def __init__(self, store, script_root, static_root):
        self.store = store
        self.script_root = FilePath(script_root)
        self.static_root = static_root

        self.silos = {}
        self.channel_request = {}
        self.pending_questions = {}


