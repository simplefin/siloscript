# Copyright (c) The SimpleFIN Team
# See LICENSE for details.

from twisted.internet import defer, reactor, protocol, task

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
            self.runFromMessage(message, ch, method)
        else:
            yield ch.basic_ack(delivery_tag=method.delivery_tag)


    @defer.inlineCallbacks
    def runFromMessage(self, message, ch, method):
        try:
            # run the script
            output = yield self.machine.run(
                message['user'],
                message['executable'],
                message['args'],
                message['env'])

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
        queue_object, consumer_tag = yield channel.basic_consume(
            queue=queue.method.queue,
            no_ack=True)
        self.lc = task.LoopingCall(self.poll_RESULT_QUEUE, queue_object,
            receiver)
        self.lc.start(self.POLL_INTERVAL)


    def unsubscribe(self):
        if self.lc:
            self.lc.stop()


    @defer.inlineCallbacks
    def poll_RESULT_QUEUE(self, queue_object, receiver):
        ch, method, properties, body = yield queue_object.get()
        message = msgpack.unpackb(body)
        receiver(message)


    @defer.inlineCallbacks
    def run(self, user, executable, args, env):
        """
        Start a run 
        """
        channel = yield self._getChannel()
        
        message = {
            'user': user,
            'executable': executable,
            'args': args,
            'env': env,
        }

        yield channel.basic_publish(
            exchange='',
            routing_key=RUN_QUEUE,
            body=msgpack.packb(message),
            properties=pika.BasicProperties(
                delivery_mode=PERSISTENT_DELIVERY,
            ))

