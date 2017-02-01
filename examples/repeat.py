#!/usr/bin/env python2

import sys, os, json, logging
sys.path.append(os.path.abspath("."))

import gevent
import msgflo

class Repeat(msgflo.Participant):
  def __init__(self, role):
    d = {
      'component': 'PythonRepeat',
      'label': 'Repeat input data without change',
      'inports': [
        { 'id': 'in', 'type': 'any' },
      ],
      'outports': [
        { 'id': 'out', 'type': 'any' },
      ],
    }
    msgflo.Participant.__init__(self, d, role)

  def process(self, inport, msg):
    self.send('out', msg.data)
    self.ack(msg)

if __name__ == '__main__':
  msgflo.main(Repeat)

