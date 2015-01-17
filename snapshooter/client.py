from gevent import monkey; monkey.patch_all(thread=False)
import pprint
import adns
import json
import itertools
import zerorpc
import multiprocessing
import pyuv
import pycares
import datetime
import os
import sys
sys.path.insert(0, os.path.realpath('../aux'))
import goz
from caresresolver import DNSResolver


# This function is specificly used to track newGOZ. This function can be replaced 
# to track a different DGA or dynamically generate a list of domains.
# This function could also read from a file if monitoring a static set of domains.
def identify_goz_domains():
    ''' Generate and resolve newGOZ (Gameover Zeus) domains
        return only resolving "live" domains
    '''
    resolving = set([])
    loop = pyuv.Loop.default_loop()
    resolver = DNSResolver(loop)
    domains = goz.get_domains()

    def my_gethostbyname_cb(result, error):
        ''' Once results are available from asynch DNS resolution, 
            if there was no error add them to a set for further analysis
        '''
        if error is None and len(result.addresses) > 0:
            resolving.add(result.name)

    for d in domains:
        resolver.gethostbyname(d, my_gethostbyname_cb)
    loop.run()
    return resolving


def process(worker, data):
    ''' Given a worker URL and some data:
            Connect to the zeroRPC worker server
            request the get_domain function from the worker
            if the worker takes too long or the connection is lost, return empty dict
    '''
    c = zerorpc.Client(timeout=120)
    c.connect(worker)
    try:
        res = c.get_domain(data)
    except (zerorpc.exceptions.RemoteError, zerorpc.exceptions.LostRemote):
        sys.stderr.write("worker failure - worker: %s\tdata: %s\n" % (worker, data))
        res = {}
    else:
        c.close()
        return res            


def main():
    ''' Send work to workers and write the output to a file
            map the data to the worker URLs
            spawn a dedicated client process for each worker
            asynchronously send work from each client to each worker
            wait for all the output from workers
            write the output to a file
    '''
    def my_client_cb(result):
        ''' Callback function for each client process in mutliprocessing.pool
            that tells the client process to write results to a file
        '''
        ts = result['ts']
        hostname = result['request']
        with open("../results/%s_%s" % (hostname, ts), 'w') as f:
            f.write(json.dumps(result))

    urls = 	['tcp://127.0.0.1:1234', 'tcp://127.0.0.1:1235', 'tcp://127.0.0.1:1236']
    urls.extend(['tcp://127.0.0.1:1237'])

    data = identify_goz_domains()
    workers = itertools.cycle(urls)
    assignments = zip(workers, data)
    pool = multiprocessing.Pool(processes=len(urls))
    results = [pool.apply_async(process, args=(worker, data), callback=my_client_cb) for worker,data in assignments]
    output = [p.get() for p in results]


if __name__ == "__main__":
    main()
