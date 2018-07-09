# exchange
A toy "coin exchange". Built as an exercise in Docker, learning Kafka, and systems architecture


![It works!](https://i.imgur.com/RBBshhq.png)

## Running
To run, you must have Docker, Docker Machine, and Docker Compose.

Clone the repo and then run:
```
docker-compose up
```
or run 
```
docker-compose up -d
```
to run the entire system as a daemon (no log output to STDOUT)

Then visit `localhost:5001` and enjoy!

## Usage
 1. Either login with an existing UserID or press "Create new user"
 2. Each user is given $1000 and 100 coins at start
 3. Put in a buy or sell order by specifying the amount of coins you wish to buy/sell and the price
 4. Watch orders come in the order book and have fun.

## Architecture

We have 3 services, `gateway`, `risk` and `match`. 
 - `gateway` is used to host the website and interface with the user through sockets. It is a simple Flask server, and both the site and the server use Socket.IO to communicate
 - `risk` is a simple service used to validate if a user can conduct a purchase or a sale.
 - `match` is a simple order filler. It does not do partial orders. Instead, it only matches exact orders (Buy for 3@$4 will be matched with a Sell for 3@$4) in order of arrival (FIFO).
In addition there are 4 more services that run:
 - Kafka and ZooKeeper -> Used for the message bus between our three core services.
 - Redis (2 databases) -> We have a database for both the user data (how much money/coins they have) and the trades that are currently being conducted.
 
## ToDo
 
This is far from fully featured:
 - [ ] Average Buy/Sell Price graph
 - [ ] Reload trade data on login
 - [ ] Reload order book on login
