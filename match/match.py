from kafka import KafkaConsumer, KafkaProducer

import uuid
import json
import redis
import sys
import logging
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

logger.info("Starting match server...")

logger.info("Waiting for Kafka init...")
time.sleep(30)

consumerRisk = KafkaConsumer('RTM',
                         group_id='RTMGroup',
                         bootstrap_servers=['kafka:9092'])
producer = KafkaProducer(bootstrap_servers='kafka:9092')

logger.info("Connecting to Redis User Table...")
userR = redis.StrictRedis(host='usersredis', port=6379, db=0)
logger.info("Connecting to Redis Trade Table...")
tradeR = redis.StrictRedis(host='tradesredis', port=6379, db=0)

logger.info("Listening for Kafka match Messages")
for matchMsg in consumerRisk:
    logger.info("Got message " + str(matchMsg.value) + " at offset " + str(matchMsg.offset))
    data = json.loads(matchMsg.value)
    if data["Type"] == "B":
        # Check to see if there are outstanding sell orders for that amount and value
        trade = tradeR.get("S|" + str(data["Amount"]) + "|" + str(data["Price"]))
        if trade:
            tradeDict = json.loads(trade)
            tradesOutstanding = tradeDict["trades"]
            tradeItem = tradesOutstanding.pop(0)

            # remove value from buyer and seller
            sellUserData = json.loads(userR.get(tradeItem["User"]))
            sellUserData["actual_cash"] = float(sellUserData["actual_cash"]) + (float(data["Amount"]) * float(data["Price"]))
            sellUserData["potential_cash"] = float(sellUserData["potential_cash"]) + (float(data["Amount"]) * float(data["Price"]))
            sellUserData["actual_coins_owned"] = float(sellUserData["actual_coins_owned"]) - float(data["Amount"])
            userR.set(tradeItem["User"], json.dumps(sellUserData))

            data["actual_cash"] = float(data["actual_cash"]) - (float(data["Amount"]) * float(data["Price"]))
            data["potential_coins_owned"] = float(data["potential_coins_owned"]) + (float(data["Amount"]))
            data["actual_coins_owned"] = float(data["actual_coins_owned"]) + float(data["Amount"])
            userR.set(data["User"], json.dumps(data))

            if len(tradesOutstanding) == 0:
                tradeR.delete("S|" + str(data["Amount"]) + "|" + str(data["Price"]))
        else:
            # See if there is a list of existing trades:
            existingTrade = tradeR.get("B|" + str(data["Amount"]) + "|" + str(data["Price"]))
            if existingTrade:
                tradeDict = json.loads(trade)
                tradeDict["trades"].append(data)
                tradeR.set("B|" + str(data["Amount"]) + "|" + str(data["Price"]), json.dumps(tradeDict))
                logger.info("Stored: " + str(tradeR.get("B|" + str(data["Amount"]) + "|" + str(data["Price"]))))
            else:
                # Create new trade with key and commit this as first value
                tradesOutstanding = []
                tradesOutstanding.append(data)
                tradeR.set("B|" + str(data["Amount"]) + "|" + str(data["Price"]), json.dumps({"trades" : tradesOutstanding}))
                logger.info("Stored: " + str(tradeR.get("B|" + str(data["Amount"]) + "|" + str(data["Price"]))))
    else:
        trade = tradeR.get("B|" + str(data["Amount"]) + "|" + str(data["Price"]))
        if trade:
            tradeDict = json.loads(trade)
            tradesOutstanding = tradeDict["trades"]
            tradeItem = tradesOutstanding.pop(0)

            # remove value from buyer and seller
            buyUserData = json.loads(userR.get(tradeItem["User"]))
            buyUserData["actual_cash"] = float(buyUserData["actual_cash"]) - (float(data["Amount"]) * float(data["Price"]))
            buyUserData["potential_coins_owned"] = float(buyUserData["potential_coins_owned"]) + float(data["Amount"])
            buyUserData["actual_coins_owned"] = float(buyUserData["actual_coins_owned"]) + float(data["Amount"])
            userR.set(tradeItem["User"], json.dumps(buyUserData))

            data["actual_cash"] = float(data["actual_cash"]) + (float(data["Amount"]) * float(data["Price"]))
            data["potential_cash"] = float(data["potential_cash"]) + (float(data["Amount"]) * float(data["Price"]))
            data["actual_coins_owned"] = float(data["actual_coins_owned"]) - float(data["Amount"])
            userR.set(data["User"], json.dumps(data))

            if len(tradesOutstanding) == 0:
                tradeR.delete("S|" + str(data["Amount"]) + "|" + str(data["Price"]))
        else:
            # See if there is a list of existing trades:
            existingTrade = tradeR.get("S|" + str(data["Amount"]) + "|" + str(data["Price"]))
            if existingTrade:
                tradeDict = json.loads(trade)
                tradeDict["trades"].append(data)
                tradeR.set("B|" + str(data["Amount"]) + "|" + str(data["Price"]), json.dumps(tradeDict))
                logger.info("Stored: " + str(tradeR.get("B|" + str(data["Amount"]) + "|" + str(data["Price"]))))
            else:
                # Create new trade with key and commit this as first value
                tradesOutstanding = []
                tradesOutstanding.append(data)
                tradeR.set("B|" + str(data["Amount"]) + "|" + str(data["Price"]), json.dumps({"trades" : tradesOutstanding}))
                logger.info("Stored: " + str(tradeR.get("B|" + str(data["Amount"]) + "|" + str(data["Price"]))))
