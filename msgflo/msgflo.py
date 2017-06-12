#!/usr/bin/env python

import sys, os, json, random, urlparse
sys.path.append(os.path.abspath("."))

from optparse import OptionParser

import logging
logging.basicConfig()
log_level = os.environ.get('MSGFLO_PYTHON_LOGLEVEL')
logger = logging.getLogger('msgflo')
if log_level:
  level = getattr(logging, log_level.upper())
  logger.setLevel(level)

import gevent
import gevent.event

# AMQP
from haigha.connection import Connection as haigha_Connection
from haigha.message import Message as haigha_Message

# MQTT
import paho.mqtt.client as mqtt

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


DEFAULT_DISCOVERY_PERIOD=60

# Interface for engine/transport implementations
class Engine(object):
    def __init__(self, broker, discovery_period=None):
        self.broker_url = broker
        self.broker_info = urlparse.urlparse(self.broker_url)
        self.discovery_period = discovery_period if discovery_period else DEFAULT_DISCOVERY_PERIOD

    def done_callback(self, done_cb):
        self._done_cb = done_cb

    def add_participant(self, participant, iips={}):
        raise NotImplementedError

    def ack_message(self, msg):
        raise NotImplementedError
    def nack_message(self, msg):
        raise NotImplementedError

    def run(self):
        raise NotImplementedError

class Message(object):
  def __init__(self, raw):
    self.buffer = raw
    self.data = raw
    self.json = None

def deliver_iips(participant):
    iips = participant._iips
    for port, data in iips.items():
        msg = Message(data)
        msg.json = data
        participant.process(port, msg)

class AmqpEngine(Engine):

  def __init__(self, broker, discovery_period=None):
    Engine.__init__(self, broker, discovery_period=discovery_period)

    # Prepare connection to AMQP broker
    vhost = self.broker_info.path or '/'
    host = self.broker_info.hostname or 'localhost'
    port = self.broker_info.port or 5672
    user = self.broker_info.username or 'guest'
    password = self.broker_info.password or 'guest'
    self._conn = haigha_Connection(transport='gevent', close_cb=self._connection_closed_cb,
                                   host=host, vhost=vhost, port=port, user=user, password=password,
                                   logger=logger)

    # Create message channel
    self._channel = self._conn.channel()
    self._channel.add_close_listener(self._channel_closed_cb)

  def add_participant(self, participant, iips={}):
    self.participant = participant
    self.participant._engine = self
    self.participant._iips = iips

    # Create and configure message exchange and queue
    for p in self.participant.definition['inports']:
      self._setup_queue(self.participant, self._channel, 'in', p)
    for p in self.participant.definition['outports']:
      self._setup_queue(self.participant, self._channel, 'out', p)

    # Deliver IIPs
    deliver_iips(self.participant)

    # Send discovery message
    def send_discovery():
      while self.participant:
        self._send_discovery(self._channel, self.participant.definition)
        delay = self.discovery_period/2.2
        gevent.sleep(delay) # yields
    gevent.Greenlet.spawn(send_discovery)

  def run(self):
    # Start message pump
    self._message_pump_greenlet = gevent.spawn(self._message_pump_greenthread)

  def ack_message(self, msg):
    self._channel.basic.ack(msg.delivery_info["delivery_tag"])

  def nack_message(self, msg):
    self._channel.basic.nack(msg.delivery_info["delivery_tag"])

  def _send(self, outport, data):
    ports = self.participant.definition['outports']
    logger.debug("Publishing to message: %s, %s, %s" % (data,outport,ports))
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
        gevent.sleep(0.1)
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
    logger.debug('sent discovery message')
    return

  def _setup_queue(self, part, channel, direction, port):
    queue = port['queue']

    def handle_input(msg):
      logger.debug("Received message: %s" % (msg,))

      msg.buffer = msg.body
      try:
        msg.json = json.loads(msg.body.decode("utf-8"))
        msg.data = msg.json # compat
      except ValueError as e:
        # Not JSON, assume binary
        msg.data = msg.buffer

      part.process(port, msg)
      return

    if 'in' in direction:
      channel.queue.declare(queue)
      channel.basic.consume(queue=queue, consumer=handle_input, no_ack=False)
      logger.debug('subscribed to %s' % queue)
    else:
      channel.exchange.declare(queue, 'fanout')
      logger.debug('created outqueue %s' % queue)

class MqttEngine(Engine):
  def __init__(self, broker):
      Engine.__init__(self, broker)

      self._client = mqtt.Client()

      if self.broker_info.username:
        self._client.username_pw_set(self.broker_info.username, self.broker_info.password)

      self._client.on_connect = self._on_connect
      self._client.on_message = self._on_message
      self._client.on_subscribe = self._on_subscribe
      host = self.broker_info.hostname
      port = self.broker_info.port
      if port is None:
        port = 1883
      self._client.connect(host, port, 60)

  def add_participant(self, participant, iips={}):
    self.participant = participant
    self.participant._engine = self
    self.participant._iips = iips

  def run(self):
    self._message_pump_greenlet = gevent.spawn(self._message_pump_greenthread)

  def _send(self, outport, data):
    ports = self.participant.definition['outports']
    serialized = json.dumps(data)
    port = [p for p in ports if outport == p['id']][0]
    queue = port['queue']
    logger.debug("Publishing message on %s" % (queue))
    self._client.publish(queue, serialized)

  # TODO: implement ACK/NACK for MQTT
  def ack_message(self, msg):
    pass
  def nack_message(self, msg):
    pass

  def _message_pump_greenthread(self):
    try:
      while self._client is not None:
        # Pump
        self._client.loop(timeout=0.1)
        # Yield to other greenlets so they don't starve
        gevent.sleep(0.1)
    finally:
      if self._done_cb:
        self._done_cb()
    return 

  def _on_connect(self, client, userdata, flags, rc):
      logging.debug("Connected with result code" + str(rc))
  
      # Subscribe to queues for inports
      subscriptions = [] # ("topic", QoS)
      for port in self.participant.definition['inports']:
        topic = port['queue']
        logging.debug('subscribing to %s' % topic)
        subscriptions.append((topic, 0))
      self._client.subscribe(subscriptions)

      # Deliver IIPs
      deliver_iips(self.participant)

      # Send discovery messsage
      def send_discovery():
        while self.participant:
          delay = self.discovery_period/2.2
          self._send_discovery(self.participant.definition)
          gevent.sleep(delay) # yields
      gevent.Greenlet.spawn(send_discovery)

  def _on_subscribe(self, client, userdata, mid, granted_qos):
      logging.debug('subscribed %s' % str(mid))

  def _on_message(self, client, userdata, mqtt_msg):
      logging.debug('got message on %s' % mqtt_msg.topic)
      port = ""
      for inport in self.participant.definition['inports']:
          if inport['queue'] == mqtt_msg.topic:
              port = inport['id']

      def notify():
          msg = Message(mqtt_msg.payload)
          try:
            msg.json = json.loads(str(mqtt_msg.payload))
            msg.data = msg.json # compat
          except ValueError as e:
            # Not JSON, assume binary
            msg.data = msg.buffer

          self.participant.process(port, msg)

      gevent.spawn(notify)

  def _send_discovery(self, definition):
    m = {
      'protocol': 'discovery',
      'command': 'participant',
      'payload': definition,
    }
    msg = json.dumps(m)
    self._client.publish('fbp', msg)
    logger.debug('sent discovery message %s' % msg)
    return

def run(participant, broker=None, done_cb=None, iips={}):
    if broker is None:
        broker = os.environ.get('MSGFLO_BROKER', 'amqp://localhost')

    engine = None
    broker_info = urlparse.urlparse(broker)
    if broker_info.scheme == 'amqp':
        engine = AmqpEngine(broker)
    elif broker_info.scheme == 'mqtt':
        engine = MqttEngine(broker)
    else:
        raise ValueError("msgflo: No engine implementation found for broker URL scheme %s" % (broker_info.scheme,))

    if done_cb:
        engine.done_callback(done_cb)
    engine.add_participant(participant, iips)
    engine.run()

    return engine

def parse(argv, defaults={}):
    parser = OptionParser(usage="%prog [options] role")
    parser.add_option("-i", "--iips", dest="iips", default='{}',
        help="Data as initial information packets", metavar='{"inportA": "inA-data", ...}')

    (options, args) = parser.parse_args(argv)
    for k, v in defaults.items():
      if k not in options:
        options[k] = v
    options.iips = json.loads(options.iips)
    options.role = args[0]

    return [options, parser]

def main(Participant, role=None):
    [config, parser] = parse(sys.argv)
    if role:
      config.role = role
    if not config.role:
      parser.error("role not specified")

    participant = Participant(config.role)
    d = participant.definition
    waiter = gevent.event.AsyncResult()
    engine = run(participant, done_cb=waiter.set, iips=config.iips)
    anon_url = "%s://%s" % (engine.broker_info.scheme, engine.broker_info.hostname)
    print "%s(%s) running on %s" % (d['role'], d['component'], anon_url)
    sys.stdout.flush()
    waiter.wait()
