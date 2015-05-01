# Copyright (c) The SimpleFIN Team
# See LICENSE for details.

from twisted.internet import defer, reactor, protocol, task

from functools import partial

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
        try:
            # open a channel, maybe
            channel_key = None
            if properties.reply_to:
                channel_key = self.machine.channel_open()
                receiver = partial(self.questionReceiver, ch, properties.reply_to)
                self.machine.channel_connect(channel_key, receiver)

            # run the script
            output = yield self.machine.run(
                message['user'],
                message['executable'],
                message['args'],
                message['env'],
                channel_key=channel_key)

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
                )
            )
        except Exception as e:
            print 'Exception', e
            raise
        finally:
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


    @defer.inlineCallbacks
    def _getChannel(self):
        channel = yield self.conn.channel()
        yield _declareThings(channel)
        defer.returnValue(channel)


    @defer.inlineCallbacks
    def subscribeToResults(self, receiver):
        """
        Register a function to be called for every run result.
        """
        channel = yield self._getChannel()
        queue = yield channel.queue_declare(exclusive=True)
        yield channel.queue_bind(
            exchange=RESULT_EXCHANGE,
            queue=queue.method.queue,
        )
        self.poll_queue(channel, queue.method.queue, receiver, {'no_ack':True})


    def stop(self):
        for lc in self._polls:
            lc.stop()


    @defer.inlineCallbacks
    def poll_queue(self, channel, queue, receiver, consume_kwargs={}):
        queue_object, consumer_tag = yield channel.basic_consume(
            queue=queue,
            **consume_kwargs)
        lc = task.LoopingCall(self._poll_queue, queue_object,
            receiver)
        self._polls.append(lc)
        lc.start(self.POLL_INTERVAL)


    @defer.inlineCallbacks
    def _poll_queue(self, queue_object, receiver):
        ch, method, properties, body = yield queue_object.get()
        message = msgpack.unpackb(body)
        receiver(message)


    @defer.inlineCallbacks
    def run(self, user, executable, args, env, question_receiver=None):
        """
        Start a run 

        @param question_receiver: A function that will be called with questions
            for a human if information isn't available in the db.
        """
        channel = yield self._getChannel()
        
        message = {
            'user': user,
            'executable': executable,
            'args': args,
            'env': env,
        }

        properties = pika.BasicProperties(
            delivery_mode=PERSISTENT_DELIVERY,
        )

        if question_receiver:
            # make a queue to receive prompts on
            result = yield channel.queue_declare(exclusive=True)
            callback_queue = result.method.queue
            properties.reply_to = callback_queue
            self.poll_queue(channel, callback_queue, question_receiver, {'no_ack':True})
            # XXX there should be a way to stop this when there are no more
            # prompts.  Otherwise, we'll have a bunch of question queues just
            # sitting here.


        yield channel.basic_publish(
            exchange='',
            routing_key=RUN_QUEUE,
            body=msgpack.packb(message),
            properties=properties)

