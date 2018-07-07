from flask import Flask, render_template, request
from flask_socketio import SocketIO, send, emit
from pykafka import KafkaClient

import uuid
import json
import redis
import sys
import logging
import time

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secretkey'
socketio = SocketIO(app)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

logger.info("Starting gateway server...")
attempts = 0
while attempts < 30:
    try:
        client = KafkaClient(hosts="kafka:9092")
        break
    except Exception:
        logger.info("Kafka not yet ready, waiting...")
        time.sleep(3)
        attempts = attempts + 1

if attempts >= 30:
    logger.error('Could not connect to Kafka', exc_info=True)
    sys.exit(-1)

if len(client.topics) == 0:
    logger.info("No topics found, waiting for Kafka init")
    time.sleep(15)

logger.info(client.topics)
riskPublishTopic = client.topics['GTR']

logger.info("Connecting to Redis User Table...")
userR = redis.StrictRedis(host='usersredis', port=6379, db=0)

def acked(err, msg):
    if err is not None:
        logger.info("Failed to deliver message: {0}: {1}"
              .format(msg.value(), err.str()))
    else:
        logger.info("Message produced: {0}".format(msg.value()))

@app.route('/', methods = ['GET', 'POST'])
def index():
    return render_template('index.html',  async_mode=socketio.async_mode)


"""
The buy and sell values take a json like this:
{
    "UserID" : b765d201-70c0-4ea7-85b0-81456574d301,
    "Type" : "B",
    "Amount" : 100,
    "Price" : 12.53
}

Put in a buy request

Buy and sell work in the same way:
    1. Parse the message json
    2. Submit the message to kafka to be validated by "risk"
"""
@socketio.on('buy')
def buy(json):
    json['sid'] = request.sid
    logger.info("Got Buy Order: " + str(json))
    with riskPublishTopic.get_producer(delivery_reports=True) as producer:
        producer.produce(str(json))
        try:
            msg, exc = producer.get_delivery_report(block=False)
            if exc is not None:
                logger.info('Failed to deliver msg {}: {}'.format(msg.partition_key, repr(exc)))
            else:
                logger.info('Successfully delivered msg {}'.format(msg.partition_key))
        except Queue.Empty:
            pass

# Put in a sell request
@socketio.on('sell')
def sell(json):
    json['sid'] = request.sid
    logger.info("Got Sell Order: " + str(json))
    with riskPublishTopic.get_producer(delivery_reports=True) as producer:
        producer.produce(str(json))
        try:
            msg, exc = producer.get_delivery_report(block=False)
            if exc is not None:
                logger.info('Failed to deliver msg {}: {}'.format(msg.partition_key, repr(exc)))
            else:
                logger.info('Successfully delivered msg {}'.format(msg.partition_key))
        except Queue.Empty:
            pass

@socketio.on('newuser')
def newuser(message):
    user = uuid.uuid4()
    emit('usercreated', str(user), room=request.sid)
    user_properties = {"coins_owned": 100}
    logger.info('Created user ' + str(user))
    userR.set(str(user), str(json.dumps(user_properties)))
    logger.info('User ' + str(user) + ' with data ' + str(userR.get(str(user))))

@socketio.on('loginuser')
def loginuser(message):
    logger.info("Attempting login of user " + message)
    if userR.get(message):
        logger.info("Successful login of user " + message)
        emit('loginsuccess', str(message), room=request.sid)
    else:
        logger.info("Failure to login user " + message)
        emit('loginfail', "", room=request.sid)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', debug=True, port=80)
