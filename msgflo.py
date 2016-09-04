#!/usr/bin/env python

import sys, os, json, random
sys.path.append(os.path.abspath("."))

import logging # TODO: use instead of print

import gevent
import gevent.event

from haigha.connection import Connection as haigha_Connection
from haigha.message import Message as haigha_Message

def addDefaultQueue(p, role):
  defaultQueue = '%s.%s' % (role, p['id'].upper())
  p.setdefault('queue', defaultQueue)
  return p

def normalizeDefinition(d, role):
  # Apply defaults
  d.setdefault('role', role)
  d.setdefault('id', d['role'] + str(random.randint(0, 99999)))
  d.setdefault('icon', 'file-word-o')
  d.setdefault('label', "")
  inports = d.setdefault('inports', [
      { 'id': 'in', 'type': 'any' }
  ])
  outports = d.setdefault('outports', [
      { 'id': 'out', 'type': 'any' }
  ])
  inports = [addDefaultQueue(p, role) for p in inports]
  outports = [addDefaultQueue(p, role) for p in outports]

  return d

class Participant:
  def __init__(self, d, role):
    self.definition = normalizeDefinition(d, role)

  def send(self, outport, outdata):
    if not self._runtime:
      return
    self._runtime._send(outport, outdata)

  def process(self, inport, inmsg):
    raise NotImplementedError('IParticipant.process()')

  def ack(self, msg):
    self._runtime._channel.basic.ack(msg.delivery_info["delivery_tag"])

  def nack(self, msg):
    self._runtime._channel.basic.nack(msg.delivery_info["delivery_tag"])

def sendParticipantDefinition(channel, definition):
  m = {
    'protocol': 'discovery',
    'command': 'participant',
    'payload': definition,
  }
  msg = haigha_Message(json.dumps(m))
  channel.basic.publish(msg, '', 'fbp')
  print 'sent discovery message', msg
  return

def setupQueue(part, channel, direction, port):
  queue = port['queue']

  def handleInput(msg):
    print "Received message: %s" % (msg,)
    sys.stdout.flush()

    msg.data = json.loads(msg.body.decode("utf-8"))
    part.process(port, msg)
    return

  if 'in' in direction:
    channel.queue.declare(queue)
    channel.basic.consume(queue=queue, consumer=handleInput, no_ack=False)
    print 'subscribed to', queue
    sys.stdout.flush()
  else:
    channel.exchange.declare(queue, 'fanout')
    print 'created outqueue', queue
    sys.stdout.flush()

# Interface for engine/transport implementations
class Engine(object):
    def __init__(self, broker):
        self.broker_url = broker

    def done_callback(self, done_cb):
        self._done_cb = done_cb

    def add_participant(self, participant):
        raise NotImplementedError

    def ack_message(self, msg):
        raise NotImplementedError
    def nack_message(self, msg):
        raise NotImplementedError

    def run(self):
        raise NotImplementedError

class AmqpEngine(Engine):

  def __init__(self, broker):
    Engine.__init__(self, broker)

    # Connect to AMQP broker with default connection and authentication
    # FIXME: respect self.broker_url
    self._conn = haigha_Connection(transport='gevent',
                                   close_cb=self._connection_closed_cb,
                                   logger=logging.getLogger())

    # Create message channel
    self._channel = self._conn.channel()
    self._channel.add_close_listener(self._channel_closed_cb)

  def add_participant(self, participant):
    self.participant = participant
    self.participant._runtime = self

    sendParticipantDefinition(self._channel, self.participant.definition)

    # Create and configure message exchange and queue
    for p in self.participant.definition['inports']:
      setupQueue(self.participant, self._channel, 'in', p)
    for p in self.participant.definition['outports']:
      setupQueue(self.participant, self._channel, 'out', p)

  def run(self):
    # Start message pump
    self._message_pump_greenlet = gevent.spawn(self._message_pump_greenthread)

  def _send(self, outport, data):
    ports = self.participant.definition['outports']
    print "Publishing message: %s, %s, %s" % (data,outport,ports)
    sys.stdout.flush()
    serialized = json.dumps(data)
    msg = haigha_Message(serialized)
    port = [p for p in ports if outport == p['id']][0]
    self._channel.basic.publish(msg, port['queue'], '')
    return
  
  def _message_pump_greenthread(self):
    try:
      while self._conn is not None:
        # Pump
        self._conn.read_frames()
        # Yield to other greenlets so they don't starve
        gevent.sleep()
    finally:
      if self._done_cb:
        self._done_cb()
    return 
  
  def _channel_closed_cb(self, ch):
    print "AMQP channel closed; close-info: %s" % (
      self._channel.close_info,)
    self._channel = None
    
    # Initiate graceful closing of the AMQP broker connection
    self._conn.close()
    return
  
  def _connection_closed_cb(self):
    print "AMQP broker connection closed; close-info: %s" % (
      self._conn.close_info,)
    self._conn = None
    return

def run(participant, broker=None, done_cb=None):
    if broker is None:
        broker = os.environ.get('MSGFLO_BROKER', 'amqp://localhost')

    engine = None
    if broker.startswith('amqp://'):
        engine = AmqpEngine(broker)
    else:
        raise ValueError("msgflo: No engine implementation found for broker URL %s" % (broker,))

    if done_cb:
        engine.done_callback(done_cb)
    engine.add_participant(participant)
    engine.run()

    return engine
