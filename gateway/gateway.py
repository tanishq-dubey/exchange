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
socketio = SocketIO(app, async_mode="threading")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

logger.info("Starting gateway server...")

logger.info("Waiting for Kafka init...")
time.sleep(30)

producer = KafkaProducer(bootstrap_servers='kafka:9092')
consumerRisk = KafkaConsumer('RTG',
                         group_id='RTGGroup',
                         bootstrap_servers=['kafka:9092'])
consumerMatch = KafkaConsumer('MTG',
                         group_id='MTGGroup',
                         bootstrap_servers=['kafka:9092'])

logger.info("Connecting to Redis User Table...")
userR = redis.StrictRedis(host='usersredis', port=6379, db=0)


@app.before_first_request
def activate_job():
    def rtgListener():
        with app.test_request_context():
            while True:
                for riskMsg in consumerRisk:
                    logger.info("Got risk message " + str(riskMsg.value) + " at offset " + str(riskMsg.offset))
                    data = jsn.loads(riskMsg.value)
                    socketio.emit('tradeerror', "Could not execute trade: " + str(data), room=data["SID"])
    def mtgListener():
        with app.test_request_context():
            while True:
                for matchMsg in consumerMatch:
                    logger.info("Got match message " + str(matchMsg.value) + " at offset " + str(matchMsg.offset))
                    matchData = jsn.loads(matchMsg.value)
                    if matchData["Type"] == "NewTrade":
                        socketio.emit("NewTrade", matchMsg.value, broadcast=True)
                    elif matchData["Type"] == "TradeComplete":
                        dSend = {"TradeID": matchData["TradeID"],
                        "actual_cash": matchData["actual_cash"], "potential_cash": matchData["potential_cash"], "actual_coins_owned": matchData["actual_coins_owned"], "potential_coins_owned": matchData["potential_coins_owned"]}
                        socketio.emit("TradeComplete", str(jsn.dumps(dSend)), room=matchData["SID"])
                    elif matchData["Type"] == "NewTradePrivate":
                        socketio.emit("NewTradePrivate", matchMsg.value, room=matchData["SID"])

    thread = threading.Thread(target=rtgListener)
    thread.start()
    threadMTG = threading.Thread(target=mtgListener)
    threadMTG.start()

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
    json['SID'] = request.sid
    json['TradeID'] = str(uuid.uuid4())
    logger.info("Got Buy Order: " + str(json))
    producer.send('GTR', jsn.dumps(json))


# Put in a sell request
@socketio.on('sell')
def sell(json):
    json['SID'] = request.sid
    json['TradeID'] = str(uuid.uuid4())
    logger.info("Got Sell Order: " + str(json) + " "  + str(type(json)))
    producer.send('GTR', jsn.dumps(json))


# User Management
@socketio.on('newuser')
def newuser(message):
    user = uuid.uuid4()
    # Potental values describe values before trade has been completed
    user_properties = {"actual_coins_owned": 100, "actual_cash": 1000, "potential_coins_owned": 100, "potential_cash": 1000, "SID": request.sid}
    logger.info('Created user ' + str(user))
    userR.set(str(user), str(jsn.dumps(user_properties)))
    user_properties["user"] = str(user)
    logger.info('User ' + str(user) + ' with data ' + str(user_properties))
    emit('usercreated', str(jsn.dumps(user_properties)), room=request.sid)


@socketio.on('loginuser')
def loginuser(message):
    logger.info("Attempting login of user " + message)
    user = userR.get(message)
    if user:
        logger.info("Successful login of user " + message)
        user = jsn.loads(user)
        user["SID"] = request.sid
        userR.set(message, jsn.dumps(user))
        user['user'] = message
        emit('loginsuccess', str(jsn.dumps(user)), room=request.sid)
    else:
        logger.info("Failure to login user " + message)
        emit('loginfail', "", room=request.sid)


if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', debug=True, port=80)
