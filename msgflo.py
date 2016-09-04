#!/usr/bin/env python

import sys, os, json, random, urlparse
sys.path.append(os.path.abspath("."))

import logging
logger = logging.getLogger('msgflo')

import gevent
import gevent.event

# AMQP
from haigha.connection import Connection as haigha_Connection
from haigha.message import Message as haigha_Message

# MQTT
import paho.mqtt.client as mqtt
import threading

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

# Interface for implementing a Participant. Main thing used by applications
class Participant:
  def __init__(self, d, role):
    self.definition = normalizeDefinition(d, role)

  def send(self, outport, outdata):
    if not self._engine:
      return
    self._engine._send(outport, outdata)

  def process(self, inport, inmsg):
    raise NotImplementedError('IParticipant.process()')

  def ack(self, msg):
    self._engine.ack_message(msg)

  def nack(self, msg):
    self._engine.nack_message(msg)


# Interface for engine/transport implementations
class Engine(object):
    def __init__(self, broker):
        self.broker_url = broker
        self.broker_info = urlparse.urlparse(self.broker_url)

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
                                   logger=logger)

    # Create message channel
    self._channel = self._conn.channel()
    self._channel.add_close_listener(self._channel_closed_cb)

  def add_participant(self, participant):
    self.participant = participant
    self.participant._engine = self

    self._send_discovery(self._channel, self.participant.definition)

    # Create and configure message exchange and queue
    for p in self.participant.definition['inports']:
      self._setup_queue(self.participant, self._channel, 'in', p)
    for p in self.participant.definition['outports']:
      self._setup_queue(self.participant, self._channel, 'out', p)

  def run(self):
    # Start message pump
    self._message_pump_greenlet = gevent.spawn(self._message_pump_greenthread)

  def ack_message(self, msg):
    self._channel.basic.ack(msg.delivery_info["delivery_tag"])

  def nack_message(self, msg):
    self._channel.basic.nack(msg.delivery_info["delivery_tag"])

  def _send(self, outport, data):
    ports = self.participant.definition['outports']
    logger.debug("Publishing message: %s, %s, %s" % (data,outport,ports))
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
    logger.debug("AMQP channel closed; close-info: %s" % (self._channel.close_info,))
    self._channel = None
    
    # Initiate graceful closing of the AMQP broker connection
    self._conn.close()
    return
  
  def _connection_closed_cb(self):
    logger.debug("AMQP broker connection closed; close-info: %s" % (self._conn.close_info,))
    self._conn = None
    return

  def _send_discovery(self, channel, definition):
    m = {
      'protocol': 'discovery',
      'command': 'participant',
      'payload': definition,
    }
    msg = haigha_Message(json.dumps(m))
    channel.basic.publish(msg, '', 'fbp')
    logger.debug('sent discovery message', msg)
    return

  def _setup_queue(self, part, channel, direction, port):
    queue = port['queue']

    def handle_input(msg):
      logger.debug("Received message: %s" % (msg,))
      sys.stdout.flush()

      msg.data = json.loads(msg.body.decode("utf-8"))
      part.process(port, msg)
      return

    if 'in' in direction:
      channel.queue.declare(queue)
      channel.basic.consume(queue=queue, consumer=handle_input, no_ack=False)
      logger.debug('subscribed to', queue)
    else:
      channel.exchange.declare(queue, 'fanout')
      logger.debug('created outqueue')
      sys.stdout.flush()

class MqttConnector(threading.Thread):
    def __init__(self, host, port, on_connect, on_message):
        threading.Thread.__init__(self)
        self.client = mqtt.Client()
        self.client.on_connect = on_connect
        self.client.on_message = on_message
        if port is None:
          port = 1883
        self.client.connect(host, port, 60)
        self.running = True

    def run(self):
        try:
            while self.running:
                self.client.loop_forever()
        except (KeyboardInterrupt, SystemExit): #when you press ctrl+c
            self.running = False
        except StopIteration:
            self.client = None

    def publish(self, topic, msg):
      self.client.publish(topic, msg)

class MqttEngine(Engine):
  def __init__(self, broker):
      Engine.__init__(self, broker)
      host = self.broker_info.hostname
      port = self.broker_info.port
      self.connector = MqttConnector(host, port, self._on_connect, self._on_message) 

  def add_participant(self, participant):
    self.participant = participant
    self.participant._engine = self

    # FIXME: send discovery message

  def run(self):
    self.connector.run()

  def _send(self, outport, msg):
      # FIXME: lookup queue in port info
      queue = 'fofo.OUT'
      self.connector.publish(queue, msg)

  # TODO: implement ACK/NACK for MQTT
  def ack_message(self, msg):
    pass
  def nack_message(self, msg):
    pass

  def _on_connect(self, client, userdata, flags, rc):
      print("Connected with result code" + str(rc))

      # FIXME: send discovery message

  def _on_message(self, client, userdata, msg):
      print(msg.topic+" "+str(msg.payload))
      def notify():
          js = json.JSONDecoder()
          print(msg.payload)
          pl = js.decode(str(msg.payload))
          pl["published_at"] = time.time() * 1000
          for sub in subscriptions[:]:
              sub.put(json.dumps(pl))

      gevent.spawn(notify)


def run(participant, broker=None, done_cb=None):
    if broker is None:
        broker = os.environ.get('MSGFLO_BROKER', 'amqp://localhost')

    engine = None
    if broker.startswith('amqp://'):
        engine = AmqpEngine(broker)
    elif broker.startswith('mqtt://'):
        engine = MqttEngine(broker)
    else:
        raise ValueError("msgflo: No engine implementation found for broker URL %s" % (broker,))

    if done_cb:
        engine.done_callback(done_cb)
    engine.add_participant(participant)
    engine.run()

    return engine
