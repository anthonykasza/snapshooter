import sys
import zmq
import zerorpc
import os
sys.path.insert(0, os.path.realpath('../'))
from worker import Worker

w = Worker(log_filename='./w4.log')
srv = zerorpc.Server(w)
srv.bind('tcp://127.0.0.1:1237')
srv.run()
