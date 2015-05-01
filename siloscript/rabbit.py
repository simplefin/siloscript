# Copyright (c) The SimpleFIN Team
# See LICENSE for details.

from twisted.internet import defer, reactor, protocol, task
from twisted.python import log

import uuid
from functools import partial
from collections import defaultdict

import msgpack
import pika
from pika.adapters import twisted_connection

PERSISTENT_DELIVERY = 2
RUN_QUEUE = 'run_queue'
DATABASE_RESULT_QUEUE = 'db_result_queue'
RESULT_EXCHANGE = 'result_exchange'


@defer.inlineCallbacks
def makeConnection(url):
    """
    Make a Twisted-style RabbitMQ Connection.
    """
    params = pika.URLParameters(url)
    cc = protocol.ClientCreator(reactor, twisted_connection.TwistedProtocolConnection, params)
    proto = yield cc.connectTCP(params.host, params.port)
    conn = yield proto.ready
    defer.returnValue(conn)


@defer.inlineCallbacks
def _declareThings(channel):
    yield channel.queue_declare(
        queue=RUN_QUEUE,
        durable=True,
    )
    yield channel.queue_declare(
        queue=DATABASE_RESULT_QUEUE,
        durable=True,
    )
    yield channel.exchange_declare(
        exchange=RESULT_EXCHANGE,
        type='fanout',
    )
    yield channel.queue_bind(
        exchange=RESULT_EXCHANGE,
        queue=DATABASE_RESULT_QUEUE,
    )
    defer.returnValue(channel)



class RabbitMachine(object):
    """
    I provide a RabbitMQ interface to a L{siloscript.server.Machine}.
    """

    POLL_INTERVAL = 0.01


    def __init__(self, machine, connection):
        """
        @param connection: As returned by L{makeConnection}
        """
        self.conn = connection
        self.machine = machine
        self.lc = None


    @defer.inlineCallbacks
    def _getChannel(self):
        channel = yield self.conn.channel()
        yield _declareThings(channel)
        defer.returnValue(channel)


    @defer.inlineCallbacks
    def start(self):
        channel = yield self._getChannel()
        
        queue_object, consumer_tag = yield channel.basic_consume(
            queue=RUN_QUEUE,
            no_ack=False)
        self.lc = task.LoopingCall(self.poll_RUN_QUEUE, queue_object)
        self.lc.start(self.POLL_INTERVAL)


    def stop(self):
        if self.lc:
            self.lc.stop()


    @defer.inlineCallbacks
    def poll_RUN_QUEUE(self, queue_object):
        ch, method, properties, body = yield queue_object.get()

        if body:
            message = msgpack.unpackb(body)
            self.runFromMessage(message, ch, method, properties)
        else:
            yield ch.basic_ack(delivery_tag=method.delivery_tag)


    @defer.inlineCallbacks
    def runFromMessage(self, message, ch, method, properties):
        log.msg('runFromMessage(%r)' % (message,), system='RabbitMachine')
        try:
            # open a channel, maybe
            receiver = None
            if properties.reply_to:
                receiver = partial(self.questionReceiver, ch, properties.reply_to)

            # run the script
            output = yield self.machine.run(
                message['user'],
                message['executable'],
                message['args'],
                message['env'],
                channel_receiver=receiver)

            log.msg('output = %r' % (output,), system='RabbitMachine')
            # send the result
            result = {
                'msg': message,
                'result': output,
            }
            yield ch.basic_publish(
                exchange=RESULT_EXCHANGE,
                routing_key='',
                body=msgpack.packb(result),
                properties=pika.BasicProperties(
                    delivery_mode=PERSISTENT_DELIVERY,
                    correlation_id=properties.correlation_id,
                )
            )
        except Exception as e:
            print 'Exception', e
            raise
        finally:
            log.msg('ack', system='RabbitMachine')
            yield ch.basic_ack(delivery_tag=method.delivery_tag)

    @defer.inlineCallbacks
    def questionReceiver(self, channel, queue, question):
        """
        Send a question through rabbit.
        """
        yield channel.basic_publish(
            exchange='',
            routing_key=queue,
            body=msgpack.packb(question))



class RabbitClient(object):
    """
    I let you submit jobs to a remote Machine.
    """

    POLL_INTERVAL = 0.01

    def __init__(self, connection):
        """
        @param connection: As returned by L{makeConnection}
        """
        self.conn = connection
        self._polls = []
        self._result_listener = None
        self._subscribers = []
        self._waiting_for_results = defaultdict(list)


    @defer.inlineCallbacks
    def subscribeToResults(self, receiver):
        """
        Register a function to be called for every run result.
        """
        log.msg('subscribeToResults', system='RabbitClient')
        self._subscribers.append(receiver)
        yield self._startListeningForResults()


    def unsubscribeFromResults(self, receiver):
        self._subscribers.remove(receiver)


    @defer.inlineCallbacks
    def _getChannel(self):
        channel = yield self.conn.channel()
        yield _declareThings(channel)
        defer.returnValue(channel)


    def stop(self):
        log.msg('stop()', system='RabbitClient')
        self._stopListeningForResults()
        for lc in list(self._polls):
            self.stopPollingQueue(lc)


    @defer.inlineCallbacks
    def _startListeningForResults(self):
        log.msg('_startListeningForResults', system='RabbitClient')
        if self._result_listener is None:
            channel = yield self._getChannel()
            queue = yield channel.queue_declare(exclusive=True)
            yield channel.queue_bind(
                exchange=RESULT_EXCHANGE,
                queue=queue.method.queue,
            )
            self._result_listener = yield self.pollQueue(channel,
                queue.method.queue, self._resultReceived, {'no_ack':True})
            log.msg('_startListeningForResults.done', system='RabbitClient')


    def _resultReceived(self, ch, method, properties, body):
        log.msg('_resultReceived: %r' % (properties.correlation_id,),
            system='RabbitClient')
        result = msgpack.unpackb(body)
        log.msg('result: %r' % (result,), system='RabbitClient')
        correlation_id = properties.correlation_id
        if correlation_id in self._waiting_for_results:
            waiters = self._waiting_for_results.pop(properties.correlation_id)
            for waiter in waiters:
                waiter.callback(result)
        for subscriber in self._subscribers:
            subscriber(result)


    def _stopListeningForResults(self):
        log.msg('_stopListeningForResults', system='RabbitClient')
        if self._result_listener:
            self._result_listener.stop()
            self._polls.remove(self._result_listener)
            self._result_listener = None


    def waitForResult(self, correlation_id):
        """
        Returns a Deferred which will fire with the message indicating that
        there's a result for the given correlation_id.
        """
        if not self._result_listener:
            raise Exception("You must call _startListeningForResults first")
        d = defer.Deferred()
        self._waiting_for_results[correlation_id].append(d)
        return d


    @defer.inlineCallbacks
    def pollQueue(self, channel, queue, receiver, consume_kwargs={}):
        queue_object, consumer_tag = yield channel.basic_consume(
            queue=queue,
            **consume_kwargs)
        lc = task.LoopingCall(self._pollQueue, queue_object,
            receiver)
        self._polls.append(lc)
        lc.start(self.POLL_INTERVAL)
        defer.returnValue(lc)


    @defer.inlineCallbacks
    def _pollQueue(self, queue_object, receiver):
        ch, method, properties, body = yield queue_object.get()
        receiver(ch, method, properties, body)


    def stopPollingQueue(self, identifier):
        log.msg('stopPollingQueue %r' % (identifier,), system='RabbitClient')
        self._polls.remove(identifier)
        identifier.stop()


    def makeSimpleReceiver(self, receiver):
        """
        Wrap a receiver that's just expecting the message body into a function
        that's suitable for L{pollQueue} (which delivers message metadata).
        """
        def f(ch, method, properties, body):
            receiver(msgpack.unpackb(body))
        return f


    @defer.inlineCallbacks
    def run(self, user, executable, args, env, question_receiver=None,
            return_result=False):
        """
        Start a run 

        @param question_receiver: A function that will be called with questions
            for a human if information isn't available in the db.
        """
        log.msg('run(%r, %r, %r, %r, %r)' % (
            user, executable, args, env, question_receiver),
            system='RabbitClient')
        channel = yield self._getChannel()
        
        message = {
            'user': user,
            'executable': executable,
            'args': args,
            'env': env,
        }

        correlation_id = str(uuid.uuid4())

        properties = pika.BasicProperties(
            delivery_mode=PERSISTENT_DELIVERY,
            correlation_id=correlation_id,
        )

        if question_receiver:
            # make a queue to receive prompts on
            question_channel = yield self._getChannel()
            result = yield question_channel.queue_declare(exclusive=True)
            callback_queue = result.method.queue
            properties.reply_to = callback_queue
            receiver = self.makeSimpleReceiver(question_receiver)
            lc = yield self.pollQueue(question_channel, callback_queue, receiver,
                {'no_ack':True})

            # close the channel after the result comes through
            r = self.waitForResult(correlation_id)
            r.addCallback(lambda x, lc: self.stopPollingQueue(lc), lc)
            r.addCallback(lambda _: question_channel.close())

        ret_d = defer.succeed(None)
        if return_result:
            yield self._startListeningForResults()
            ret_d = self.waitForResult(correlation_id)

        yield channel.basic_publish(
            exchange='',
            routing_key=RUN_QUEUE,
            body=msgpack.packb(message),
            properties=properties)

        yield channel.close()

        ret = yield ret_d
        defer.returnValue(ret)

