# Copyright (c) The SimpleFIN Team
# See LICENSE for details.

from twisted.internet import defer
from klein import Klein
from twisted.python import log
from twisted.python.filepath import FilePath
from twisted.internet import utils
from twisted.web.static import File
import sys

import json
from functools import partial
from uuid import uuid4

from siloscript.storage import MemoryStore, Silo




def sseMsg(name, data):
    return 'event: %s\ndata: %s\n\n' % (name, json.dumps(data))




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

    @app.route('/static', methods=['GET'], branch=True)
    def static(self, request):
        return File(self.static_root)


    @app.route('/channel/open', methods=['GET'])
    def channel_open(self, request):
        """
        Create a new channel for a user to receive questions.
        """
        channel_key = str(uuid4())
        return channel_key


    @app.route('/channel/<string:channel_key>/events', methods=['GET'])
    def channel_events(self, request, channel_key):
        request.setHeader('Content-type', 'text/event-stream')
        request.write(sseMsg('channel_key', channel_key))

        def rm(result, channel_key):
            self.channel_request.pop(channel_key)

        d = defer.Deferred()
        self.channel_request[channel_key] = {
            'req': request,
            'd': d,
        }
        
        request.notifyFinish().addCallback(rm, channel_key)
        return d


    @app.route('/question/<string:question_id>', methods=['POST'])
    def answer_question(self, request, question_id):
        """
        Answer a question posed to a user.
        """
        answer = request.content.read()
        question = self.pending_questions.pop(question_id)
        question['d'].callback(answer)


    def _askQuestion(self, channel_key, prompt):
        """
        Send a request to a user over the channel and wait for a response.

        @param channel_key: The channel to ask.
        @param prompt: The human-readable string to present to the user.

        @return: A Deferred which fires with a response when there is one.
        """
        d = defer.Deferred()

        question_id = str(uuid4())
        self.pending_questions[question_id] = {
            'id': question_id,
            'prompt': prompt,
            'd': d,
        }

        if channel_key not in self.channel_request:
            # XXX there is no user available to answer the question
            d.callback(defer.fail(Exception('No user')))
        else:
            # ask the connected user for the answer.
            channel = self.channel_request[channel_key]
            channel['req'].write(sseMsg('question', {
                'id': question_id,
                'prompt': prompt,
            }))
        return d


    @app.route('/run/<string:user>', methods=['POST'])
    @defer.inlineCallbacks
    def run(self, request, user):
        """
        Run a script for a user.
        """
        script = request.args.get('script', [None])[0]
        channel_key = request.args.get('channel_key', [None])[0]
        args = json.loads(request.args.get('args', ["[]"])[0])

        log.msg('script: %r, channel_key: %r, args: %r' % (
            script, channel_key, args))
        if not script:
            log.msg('No script', request.content.read())
            request.setResponseCode(400)
            return        

        script_fp = self.script_root
        try:
            for segment in script.split('/'):
                script_fp = script_fp.child(segment)
        except:
            request.setResponseCode(400)
            return

        access_key = self.mkSilo(user, script, channel_key)

        env = {
            'DATASTORE_URL': '%s/data/%s' % (self.my_root, access_key),
        }
        out, err, exit = yield utils.getProcessOutputAndValue(script_fp.path,
            args, env=env)

        channel = self.channel_request.get(channel_key, None)
        if channel:
            channel['d'].callback(None)
        defer.returnValue(out)


    def mkSilo(self, user_id, sub_key, channel_key=None):
        """
        Make a silo tied to a particular user and sub_key.
        """
        func = None
        if channel_key:
            func = partial(self._askQuestion, channel_key)
        silo = Silo(self.store, user_id, sub_key, func)
        key = str(uuid4())
        self.silos[key] = silo
        return key


    #----------------------------------------------------------------------
    # the interface scripts use
    #----------------------------------------------------------------------

    @app.route('/data/<string:access_key>/<string:key>', methods=['GET'])
    @defer.inlineCallbacks
    def data_GET(self, request, access_key, key):
        silo = self.silos[access_key]
        prompt = request.args.get('prompt', [None])[0]

        try:
            log.msg('checking silo: %r' % (key,))
            value = yield silo.get(key, prompt=prompt)
            defer.returnValue(value)
        except KeyError:
            log.msg('not present')
            request.setResponseCode(404)



if __name__ == '__main__':
    log.startLogging(sys.stdout)
    store = MemoryStore()
    server = UIServer(store, 'scripts', static_root='static')
    server.app.run('0.0.0.0', 9600)
