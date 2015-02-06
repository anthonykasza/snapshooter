import ast
import pprint
import urllib2
import json
import itertools
import os
import sys
import pika
import uuid

def grab_c2_domains():
    ''' Grab Bambenek C2 domains
    '''
    fields = ['name', 'reasom', 'ts', 'url']
    domains = set()
    url = urllib2.urlopen("http://osint.bambenekconsulting.com/feeds/c2-dommasterlist.txt")
    raw = url.read().strip().split("\n")
    for line in raw:
        if line.startswith('#') or line == '':
            continue
        line = dict(zip(fields, line.split(',')))
        if line['name'] != '':
            domains.add(line['name'])
    return domains

class SnapShooterClient(object):
    def __init__(self):
        self.connection = pika.BlockingConnection(pika.ConnectionParameters(
                host='localhost'))
        self.channel = self.connection.channel()
        result = self.channel.queue_declare(exclusive=True)
        self.callback_queue = result.method.queue
        self.channel.basic_consume(self.on_response, no_ack=True,
                                   queue=self.callback_queue)

    def on_response(self, ch, method, props, body):
        if self.corr_id == props.correlation_id:
            self.response = body

    def call(self, n):
        self.response = None
        self.corr_id = str(uuid.uuid4())
        self.channel.basic_publish(exchange='',
                                   routing_key='rpc_queue',
                                   properties=pika.BasicProperties(
                                         reply_to = self.callback_queue,
                                         correlation_id = self.corr_id,
                                         ),
                                   body=str(n))
        while self.response is None:
            self.connection.process_data_events()
        return self.response


def main():
    def response_cb(r):
        r = ast.literal_eval(r)
        ts = r['ts']
        hostname = r['request']
        with open("../results/%s_%s" % (hostname, ts), 'w') as f:
            f.write(json.dumps(r))

    snap_client = SnapShooterClient()
    domains = ["cnn.com", "reddit.com"]
#    domains = grab_c2_domains()
    for domain in domains:
        print " [x] Requesting: %s" % (domain)
        response = snap_client.call(domain)
        print " [.] Writing response for %s to file" % (domain)
        response_cb(response)


if __name__ == "__main__":
    main()
