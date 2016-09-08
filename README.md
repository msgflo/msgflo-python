# msgflo-python: Python participant support for MsgFlo

[MsgFlo](https://github.com/msgflo/msgflo) is a distributed, polyglot FBP (flow-based-programming) runtime.
It integrates with other FBP tools like the [Flowhub](http://flowhub.io) visual programming IDE.
This library makes it easy to create MsgFlo participants in Python.

msgflo-python currently supports Python 2 and is built on top of [gevent](http://www.gevent.org/).
It uses [Haigha](https://github.com/agoragames/haigha) for AMQP support
and [Eclipse Paho](https://eclipse.org/paho/clients/python/) for MQTT.

## Status

*Experimental*

* Basic support for setting up and running Participants
* Support for AMQP/RabbitMQ and MQTT brokers

## License

MIT, see [./LICENSE](./LICENSE)

## Installing

Get it from [PyPi](http://pypi.python.org/)

    pip install msgflo --user

## Usage

See [./examples/repeat.py](./examples/repeat.py)

    wget https://github.com/msgflo/msgflo-python/raw/master/examples/repeat.py
    # Set address of broker to connect to. Can also be amqp://...
    export MSGFLO_BROKER=mqtt://localhost
    python ./repeat.py
