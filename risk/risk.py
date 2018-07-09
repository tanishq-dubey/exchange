from kafka import KafkaConsumer, KafkaProducer

import uuid
import json
import redis
import sys
import logging
import time


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

logger.info("Starting risk server...")

logger.info("Waiting for Kafka init...")
time.sleep(30)

consumerRisk = KafkaConsumer('GTR',
                         group_id='GTRGroup',
                         bootstrap_servers=['kafka:9092'])
producer = KafkaProducer(bootstrap_servers='kafka:9092')

logger.info("Connecting to Redis User Table...")
userR = redis.StrictRedis(host='usersredis', port=6379, db=0)

logger.info("Listening for Kafka risk Messages")
while True:
    for riskMsg in consumerRisk:
        logger.info("Got message " + str(riskMsg.value) + " at offset " + str(riskMsg.offset))
        data = json.loads(riskMsg.value)
        # Check to see the transaction type
        userData = json.loads(userR.get(data["User"]))
        if data["Type"] == "B":
            val = float(data["Amount"]) * float(data["Price"])
            if val > float(userData["potential_cash"]):
                logger.info("Buy order was invalid...(" + str(userData) + ")")
                retData = {"Type": "Invalid", "sid": data["sid"]}
                producer.send('RTG', json.dumps(retData))
            else:
                logger.info("Buy order sent to matcher...")
                # Remove the value from the potential
                userData["potential_cash"] = float(userData["potential_cash"]) - val
                userR.set(data["User"], str(json.dumps(userData)))
                producer.send('RTM', riskMsg.value)
        else:
            val =  float(data["Amount"])
            if val > float(userData["potential_coins_owned"]):
                logger.info("Sell order was invalid...(" + str(userData) + ")")
                retData = {"Type": "Invalid", "sid": data["sid"]}
                producer.send('RTG', json.dumps(retData))
            else:
                logger.info("Sell order sent to matcher...")
                userData["potential_coins_owned"] = float(userData["potential_coins_owned"]) - val
                userR.set(data["User"], str(json.dumps(userData)))
                producer.send('RTM', riskMsg.value)
