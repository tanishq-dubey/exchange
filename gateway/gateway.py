from flask import Flask, render_template, request
from flask_socketio import SocketIO, send, emit
from pykafka import KafkaClient
import time

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secretkey'
socketio = SocketIO(app)

time.sleep(30)

client = KafkaClient(hosts="kafka:9092")
print(client.topics)
riskPublishTopic = client.topics['GTR']

def acked(err, msg):
    if err is not None:
        print("Failed to deliver message: {0}: {1}"
              .format(msg.value(), err.str()))
    else:
        print("Message produced: {0}".format(msg.value()))

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
"""

"""
Put in a buy request

Buy and sell work in the same way:
    1. Parse the message json
    2. Submit the message to kafka to be validated by "risk"
"""
@socketio.on('buy')
def buy(json):
    print(request.sid)
    print(json)
    print(str(json))

    with riskPublishTopic.get_producer(delivery_reports=True) as producer:
        producer.produce(str(json))
        try:
            msg, exc = producer.get_delivery_report(block=False)
            if exc is not None:
                print 'Failed to deliver msg {}: {}'.format(msg.partition_key, repr(exc))
            else:
                print 'Successfully delivered msg {}'.format(msg.partition_key)
        except Queue.Empty:
            pass

# Put in a sell request
@socketio.on('sell')
def sell(json):
    pass

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', debug=True, port=80)
