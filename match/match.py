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
while True:
    for matchMsg in consumerRisk:
        logger.info("Got message " + str(matchMsg.value) + " at offset " + str(matchMsg.offset))
        data = json.loads(matchMsg.value)
        if data["Type"] == "B":
            # Check to see if there are outstanding sell orders for that amount and value
            trade = tradeR.get("S|" + str(data["Amount"]) + "|" + str(data["Price"]))
            if trade:
                logger.info("Existing opposite trade found: " + str(trade) + " DEBUG: " + str(type(trade)))
                tradeDict = json.loads(trade)
                tradesOutstanding = tradeDict["trades"]
                tradeItem = tradesOutstanding.pop(0)

                # remove value from buyer and seller
                sellUserData = json.loads(userR.get(tradeItem["User"]))
                sellUserData["actual_cash"] = float(sellUserData["actual_cash"]) + (float(data["Amount"]) * float(data["Price"]))
                sellUserData["potential_cash"] = float(sellUserData["potential_cash"]) + (float(data["Amount"]) * float(data["Price"]))
                sellUserData["actual_coins_owned"] = float(sellUserData["actual_coins_owned"]) - float(data["Amount"])
                userR.set(tradeItem["User"], json.dumps(sellUserData))

                buyUserData = json.loads(userR.get(data["User"]))
                buyUserData["actual_cash"] = float(buyUserData["actual_cash"]) - (float(data["Amount"]) * float(data["Price"]))
                buyUserData["potential_coins_owned"] = float(buyUserData["potential_coins_owned"]) + (float(data["Amount"]))
                buyUserData["actual_coins_owned"] = float(buyUserData["actual_coins_owned"]) + float(data["Amount"])
                userR.set(data["User"], json.dumps(buyUserData))

                if len(tradesOutstanding) == 0:
                    tradeR.delete("S|" + str(data["Amount"]) + "|" + str(data["Price"]))

                logger.info("Sending back to gateway")
                # Publish data to gateway
                # UserID, TradeID, SID, updated user values
                # We publish twice, once for buyer, once for seller
                bData = {"Type": "TradeComplete", "User": data["User"], "TradeID": data["TradeID"], "SID": buyUserData["SID"], "actual_cash": buyUserData["actual_cash"], "potential_coins_owned": buyUserData["potential_coins_owned"], "actual_coins_owned": buyUserData["actual_coins_owned"], "potential_cash": buyUserData["potential_cash"]}
                producer.send("MTG", str(json.dumps(bData)))

                sData = {"Type": "TradeComplete", "User": tradeItem["User"], "TradeID": tradeItem["TradeID"], "SID": sellUserData["SID"], "actual_cash": sellUserData["actual_cash"], "potential_cash": sellUserData["potential_cash"], "actual_coins_owned": sellUserData["actual_coins_owned"], "potential_coins_owned": sellUserData["potential_coins_owned"]}
                producer.send("MTG", str(json.dumps(sData)))

            else:
                # See if there is a list of existing trades:
                existingTrade = tradeR.get("B|" + str(data["Amount"]) + "|" + str(data["Price"]))
                if existingTrade:
                    logger.info("Existing trade found: " + str(existingTrade))
                    tradeDict = json.loads(existingTrade)
                    tradeDict["trades"].append(data)
                    tradeR.set("B|" + str(data["Amount"]) + "|" + str(data["Price"]), json.dumps(tradeDict))
                    logger.info("Stored: " + str(tradeR.get("B|" + str(data["Amount"]) + "|" + str(data["Price"]))))
                else:
                    # Create new trade with key and commit this as first value
                    tradesOutstanding = []
                    tradesOutstanding.append(data)
                    tradeR.set("B|" + str(data["Amount"]) + "|" + str(data["Price"]), json.dumps({"trades" : tradesOutstanding}))
                    logger.info("Stored: " + str(tradeR.get("B|" + str(data["Amount"]) + "|" + str(data["Price"]))))

                # Publish that a uncompleted trade has been made, this is anon data that is broadcast, just type, price and amount
                pData = {"Type": "NewTrade", "TradeType": "B", "Amount": data["Amount"], "Price": data["Price"]}
                producer.send("MTG", str(json.dumps(pData)))

                # Private publish to the buyer/seller to indicate that a trade is in progress
                pData = {"Type": "NewTradePrivate", "TradeType": "B", "Amount": data["Amount"], "Price": data["Price"], "TradeID": data["TradeID"], "SID": data["SID"]}
                producer.send("MTG", str(json.dumps(pData)))


        else:
            trade = tradeR.get("B|" + str(data["Amount"]) + "|" + str(data["Price"]))
            if trade:
                logger.info("Existing opposite trade found: " + str(trade) + " DEBUG: " + str(type(trade)))
                tradeDict = json.loads(trade)
                tradesOutstanding = tradeDict["trades"]
                tradeItem = tradesOutstanding.pop(0)

                # remove value from buyer and seller
                buyUserData = json.loads(userR.get(tradeItem["User"]))
                buyUserData["actual_cash"] = float(buyUserData["actual_cash"]) - (float(data["Amount"]) * float(data["Price"]))
                buyUserData["potential_coins_owned"] = float(buyUserData["potential_coins_owned"]) + float(data["Amount"])
                buyUserData["actual_coins_owned"] = float(buyUserData["actual_coins_owned"]) + float(data["Amount"])
                userR.set(tradeItem["User"], json.dumps(buyUserData))

                sellUserData = json.loads(userR.get(data["User"]))
                sellUserData["actual_cash"] = float(sellUserData["actual_cash"]) + (float(data["Amount"]) * float(data["Price"]))
                sellUserData["potential_cash"] = float(sellUserData["potential_cash"]) + (float(data["Amount"]) * float(data["Price"]))
                sellUserData["actual_coins_owned"] = float(sellUserData["actual_coins_owned"]) - float(data["Amount"])
                userR.set(data["User"], json.dumps(sellUserData))

                if len(tradesOutstanding) == 0:
                    tradeR.delete("S|" + str(data["Amount"]) + "|" + str(data["Price"]))

                bData = {"Type": "TradeComplete", "User": tradeItem["User"], "TradeID": tradeItem["TradeID"], "SID": buyUserData["SID"], "actual_cash": buyUserData["actual_cash"], "potential_coins_owned": buyUserData["potential_coins_owned"], "actual_coins_owned": buyUserData["actual_coins_owned"], "potential_cash": buyUserData["potential_cash"]}
                producer.send("MTG", str(json.dumps(bData)))

                sData = {"Type": "TradeComplete", "User": data["User"], "TradeID": data["TradeID"], "SID": sellUserData["SID"], "actual_cash": sellUserData["actual_cash"], "potential_cash": sellUserData["potential_cash"], "actual_coins_owned": sellUserData["actual_coins_owned"], "potential_coins_owned": sellUserData["potential_coins_owned"]}
                producer.send("MTG", str(json.dumps(sData)))
            else:
                # See if there is a list of existing trades:
                existingTrade = tradeR.get("S|" + str(data["Amount"]) + "|" + str(data["Price"]))
                if existingTrade:
                    logger.info("Existing trade found: " + str(existingTrade))
                    tradeDict = json.loads(existingTrade)
                    tradeDict["trades"].append(data)
                    tradeR.set("S|" + str(data["Amount"]) + "|" + str(data["Price"]), json.dumps(tradeDict))
                    logger.info("Stored: " + str(tradeR.get("B|" + str(data["Amount"]) + "|" + str(data["Price"]))))
                else:
                    # Create new trade with key and commit this as first value
                    tradesOutstanding = []
                    tradesOutstanding.append(data)
                    tradeR.set("S|" + str(data["Amount"]) + "|" + str(data["Price"]), json.dumps({"trades" : tradesOutstanding}))
                    logger.info("Stored: " + str(tradeR.get("B|" + str(data["Amount"]) + "|" + str(data["Price"]))))

                pData = {"Type": "NewTrade", "TradeType": "S", "Amount": data["Amount"], "Price": data["Price"]}
                producer.send("MTG", str(json.dumps(pData)))

                # Private publish to the buyer/seller to indicate that a trade is in progress
                pData = {"Type": "NewTradePrivate", "TradeType": "S", "Amount": data["Amount"], "Price": data["Price"], "TradeID": data["TradeID"], "SID": data["SID"]}
                producer.send("MTG", str(json.dumps(pData)))
