
# msgflo-python 0.4.0 - released 22.11.2017

* MQTT: Support for TLS encryption and authentication.
Use the mqtts:// protocol scheme in `MSGFLO_BROKER` urls.
Optionionally can specify query parameters which are passed to [tls_set() in paho-mqtt](https://pypi.python.org/pypi/paho-mqtt#option-functions): `ca_certs` to specify trusted CA certsm, and `privkey` + `certfile` for key-based authentication.

# msgflo-python 0.3.0 - released 21.11.2017

* BREAKING. Change default topic convention to role/port from role.PORT.
To have the same format as before, specify the `queue` property of port definition explicitly.
* MqttEngine: Fix support for multiple participants using `add_participant()`

# msgflo-python 0.2.0 - released 13.11.2017

* Support for Python 3 (MQTT only)

# msgflo-python 0.1.0 - released 12.06.2017

* Also provide port name in `process()`

# msgflo-python 0.0.5 - released 08.09.2016

* Support for MQTT v3.1.1

# msgflo-python 0.0.1 - released 04.06.2015

* First release
