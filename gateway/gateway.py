from flask import Flask, render_template, request
from flask_socketio import SocketIO, send, emit
from kafka import KafkaConsumer, KafkaProducer

import uuid
import json as jsn
import redis
import sys
import logging
import time
import threading

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secretkey'
socketio = SocketIO(app)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

logger.info("Starting gateway server...")

logger.info("Waiting for Kafka init...")
time.sleep(30)

producer = KafkaProducer(bootstrap_servers='kafka:9092')
consumerRisk = KafkaConsumer('RTG',
                         group_id='RTGGroup',
                         bootstrap_servers=['kafka:9092'])

logger.info("Connecting to Redis User Table...")
userR = redis.StrictRedis(host='usersredis', port=6379, db=0)

def rtgListener():
    for riskMsg in consumerRisk:
        logger.info("Got message " + str(riskMsg.value) + " at offset " + str(riskMsg.offset))
        data = jsn.loads(riskMsg.value)
        emit('tradeerror', "Could not execute trade: " + str(data), room=data["sid"])

logger.info("Start kafka listener")
t1 = threading.Thread(target=rtgListener)
t1.start()

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
    producer.send('GTR', jsn.dumps(json))


# Put in a sell request
@socketio.on('sell')
def sell(json):
    json['sid'] = request.sid
    logger.info("Got Sell Order: " + str(json) + " "  + str(type(json)))
    producer.send('GTR', jsn.dumps(json))


# User Management
@socketio.on('newuser')
def newuser(message):
    user = uuid.uuid4()
    emit('usercreated', str(user), room=request.sid)
    user_properties = {"coins_owned": 100, "cash": 1000}
    logger.info('Created user ' + str(user))
    userR.set(str(user), str(jsn.dumps(user_properties)))
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



