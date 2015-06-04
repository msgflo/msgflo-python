msgflo = require 'msgflo'
path = require 'path'
chai = require 'chai' unless chai
heterogenous = require '../node_modules/msgflo/spec/heterogenous.coffee'

python = process.env.PYTHON or 'python'
participants =
  'PythonRepeat': [python, path.join __dirname, '..', 'examples', 'repeat.py']

describe 'Participants', ->
  address = 'amqp://localhost'
  g =
    broker: null
    commands: participants

  beforeEach (done) ->
    g.broker = msgflo.transport.getBroker address
    g.broker.connect done
  afterEach (done) ->
    g.broker.disconnect done

  names = Object.keys g.commands
  names.forEach (name) ->
    heterogenous.testParticipant g, name



