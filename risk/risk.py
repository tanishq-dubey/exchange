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
for riskMsg in consumerRisk:
    logger.info("Got message " + str(riskMsg.value) + " at offset " + str(riskMsg.offset))
    data = json.loads(riskMsg.value)
    # Check to see the transaction type
    userData = json.loads(userR.get(data["User"]))
    if data["Type"] == "B":
        val = float(data["Amount"]) * float(data["Price"])
        if val > float(userData["cash"]):
            producer.send('RTG', b'{"Type": "invalid"}')
        else:
            producer.send('RTM', riskMsg.value)
    else:
        val =  float(data["Amount"])
        if val > float(userData["coins_owned"]):
            producer.send('RTG', b'{"Type": "invalid"}')
        else:
            producer.send('RTM', riskMsg.value)
