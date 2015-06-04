#!/usr/bin/env python

import sys, os, json, logging
sys.path.append(os.path.abspath("."))

import gevent
import msgflo

class Repeat(msgflo.Participant):
  def __init__(self, role):
    d = {
      'component': 'PythonRepeat',
      'label': 'Repeat input data without change',
    }
    msgflo.Participant.__init__(self, d, role)

  def process(self, inport, msg):
    self.send('out', msg.data)
    self.ack(msg)


def main():
  waiter = gevent.event.AsyncResult()
  
  p = Repeat('repeat')
  msgflo.GeventEngine(p, waiter.set)
  
  print "Running"
  sys.stdout.flush()
  waiter.wait()
  print "Shutdown"
  sys.stdout.flush()

if __name__ == '__main__':
  logging.basicConfig()
  main()

