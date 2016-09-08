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

## Usage

See [./examples/repeat.py](./examples/repeat.py)

Run in git

    pip install -r requirements.pip -t .
    python ./examples/repeat.py

## License

MIT, see [./LICENSE](./LICENSE)
