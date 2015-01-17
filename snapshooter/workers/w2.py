import sys
import zmq
import zerorpc
import os
sys.path.insert(0, os.path.realpath('../'))
from worker import Worker

w = Worker(log_filename='./w2.log')
srv = zerorpc.Server(w)
srv.bind('tcp://127.0.0.1:1235')
srv.run()
