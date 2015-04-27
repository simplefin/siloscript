# Copyright (c) The SimpleFIN Team
# See LICENSE for details.

from twisted.internet import defer
from klein import Klein
from twisted.web.static import File

import hashlib

import json
from functools import partial, wraps
from collections import defaultdict
from uuid import uuid4

from siloscript.storage import Silo
from siloscript.util import async
from siloscript.error import NotFound, InvalidKey, CryptError



class Machine(object):
    """
    I coordinate the running scripts that want user input and users that
    are ready to give it.

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
        Create a new channel on which to receive questions.
        """
        key = 'CH-%s' % (uuid4(),)
        self.channels.add(key)
        return key


    def channel_connect(self, channel_key, receiver):
        """
        Register a function to be called for each question sent to a channel.

        @param channel_key: A channel key as returned by L{channel_open}.
        @param receiver: A function that will be called with a single argument:
            a dictionary with an C{'id'} and C{'prompt'}.  The function should
            call L{answer_question} to provide the answer.
        """
        if channel_key not in self.channels:
            raise KeyError("No such channel")
        self.receivers[channel_key].append(receiver)
        for question in list(self.pending_questions_by_channel[channel_key]):
            receiver(question['data'])


    def channel_disconnect(self, channel_key, receiver):
        """
        Opposite of L{channel_connect}.
        """
        self.receivers[channel_key].remove(receiver)


    def channel_notifyClosed(self, channel_key):
        """
        Return a Deferred which will fire when the given channel is closed.
        If no such channel exists, the Deferred will fire immediately.

        @param channel_key: A channel key as returned by L{channel_open}.
        """
        if channel_key not in self.channels:
            return defer.succeed(None)
        d = defer.Deferred()
        self.pending_channelClosed_notifications[channel_key].append(d)
        return d


    def channel_close(self, channel_key):
        """
        Close a channel so that it won't receive any more questions.

        @param channel_key: A channel key as returned by L{channel_open}.
        """
        if channel_key in self.channels:
            self.channels.remove(channel_key)
        for d in self.pending_channelClosed_notifications[channel_key]:
            d.callback(channel_key)


    def channel_prompt(self, channel_key, question):
        """
        Ask a question of a channel.

        @param channel_key: A channel key as returned by L{channel_open}.
        @param question: A dict question with at least a C{'prompt'}
            string and possibly some C{'options'}.

        @return: A L{Deferred} which will fire with the answer if one is
            given.
        """
        question_id = 'Q-%s' % (uuid4(),)
        
        answer_d = defer.Deferred()
        q = {
            'channel_key': channel_key,
            'd': answer_d,
            'data': {
                'id': question_id,
                'prompt': question['prompt'],
            },
        }
        if 'options' in question:
            q['data']['options'] = question['options']
        self.pending_questions_by_id[question_id] = q
        self.pending_questions_by_channel[channel_key].append(q)

        for receiver in self.receivers[channel_key]:
            receiver(q['data'])

        return answer_d


    def answer_question(self, question_id, answer):
        """
        Answer a question posed by L{channel_prompt} and eventually received
        by receivers registered with L{channel_connect}.

        @param question_id: Id of question that was sent to receiver.
        @param answer: string answer.
        """
        question = self.pending_questions_by_id.pop(question_id)
        self.pending_questions_by_channel[question['channel_key']]\
            .remove(question)
        question['d'].callback(answer)



    def control_makeSilo(self, user, subkey, channel_key=None):
        """
        Create a data silo scoped to the given C{user} and C{subkey}.

        The caller is responsible to do any authentication/authorization
        of this user for this subkey.

        @param user: string user identifier.
        @param subkey: string subkey identifier.  
        @param channel_key: optional channel key (as returned by
            L{channel_open}) if user input will be available when data is
            requested and not available from the data store.

        @return: string silo key.
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
        Close a silo so that no more reads/writes can be done on it.

        @param silo_key: A string silo key as returned by L{control_makeSilo}.
        """
        self.silos.pop(silo_key)
        channel_key = self.silo_channel.pop(silo_key)
        self.channel_close(channel_key)


    def run(self, user, executable, args, env, channel_key=None, logger=None):
        """
        Create a data silo for the given user and script, then run the script.

        The caller is responsible for authenticating the user.

        @param user: string user identifer.
        @param executable: script name to run
        @param args: additional command-line args for execution.
        @param env: additional environment variable to set for script.
        @param channel_key: If user input is available, this is a channel_key
            as returned by L{channel_open}.  See also L{control_makeSilo}.
        @param logger: Logging function to be given messages as it goes.

        @return: the (L{Deferred}) stdout, stderr, rc of the process or else
            a failure.
        """
        silo_key = self.control_makeSilo(user, executable, channel_key)
        def cleanup(result):
            self.control_closeSilo(silo_key)
            return result
        d = self.runner.runWithSilo(
            silo_key=silo_key,
            executable=executable,
            args=args,
            env=env,
            logger=logger)
        d.addBoth(cleanup)
        return d


    def _data_validateUserSuppliedKey(self, key):
        """
        Validate that the given user key is okay.
        """
        if key.startswith(self.invalid_key_prefix):
            raise InvalidKey('Invalid key: %r' % (key,))


    @async
    def data_get(self, silo_key, key, prompt=None, save=True, options=None):
        """
        Get data from a user-scoped silo.

        @param silo_key: A key as returned by L{control_makeSilo}.
        @param key: string key identifing data wanted.
        @param prompt: If given, this is a human-friendly string to be used to
            prompt a user for the value in case it's no in the datastore
            already.
        @param save: If C{False}, only prompt and don't save the response.
        @param options: List of possible values.  Not enforced.

        @return: The L{Deferred} value (either cached or from the user).
        """
        if silo_key not in self.silos:
            raise NotFound(silo_key)
        self._data_validateUserSuppliedKey(key)
        return self.silos[silo_key].get(key, prompt, save=save,
            options=options)


    @async
    def data_put(self, silo_key, key, value):
        """
        Put a value in the user-scope silo.

        @param silo_key: A key as returned by L{control_makeSilo}.
        @param key: string key of data.
        @param value: string value of data.
        """
        if silo_key not in self.silos:
            raise NotFound(silo_key)
        self._data_validateUserSuppliedKey(key)
        return self.silos[silo_key].put(key, value)


    @defer.inlineCallbacks
    def data_createToken(self, silo_key, value):
        """
        Exchange a piece of data for a consistent, opaque token.  This is
        useful for sensitive pieces of data, such as bank account credentials,
        or a social security number.  The resulting value is random and not
        derived from the given value in any way.

        @param silo_key: A key as returned by L{control_makeSilo}.
        @param value: The probably sensitive piece of data you want to
            tokenize.
        """
        if silo_key not in self.silos:
            raise NotFound(silo_key)
        silo = self.silos[silo_key]
        key = ':tokens'
        try:
            data = yield silo.get(key)
            current_tokens = json.loads(data)
        except KeyError:
            current_tokens = {}

        h = hashlib.sha1(value + self.token_salt).hexdigest()
        if h in current_tokens:
            defer.returnValue(current_tokens[h])

        token = 'TK-%s' % (uuid4(),)
        current_tokens[h] = token
        yield silo.put(key, json.dumps(current_tokens))
        defer.returnValue(token)



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


    @app.handle_errors(NotFound, KeyError)
    def notfound(self, request, error):
        request.setResponseCode(404)
        return ''


    @app.handle_errors(CryptError)
    def crypt_error(self, request, error):
        request.setResponseCode(500)
        return 'Error, try again later.'


    @app.route('/<string:silo_key>/<string:key>', methods=['GET'])
    def data_GET(self, request, silo_key, key):
        prompt = request.args.get('prompt', [None])[0]
        save = request.args.get('save', ['True'])[0] == 'True'
        options = request.args.get('options', None)
        return self.machine.data_get(silo_key, key, prompt,
            save=save, options=options)


    @app.route('/<string:silo_key>/<string:key>', methods=['PUT'])
    def data_PUT(self, request, silo_key, key):
        value = request.content.read()
        return self.machine.data_put(silo_key, key, value)


    @app.route('/<string:silo_key>', methods=['POST'])
    def data_getID(self, request, silo_key):
        value = request.args.get('value', [''])[0]
        return self.machine.data_createToken(silo_key, value)



