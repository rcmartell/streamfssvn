import sys, Pyro4
from time import sleep
QUEUE_SIZE = 65536
Pyro4.config.ONEWAY_THREADED = True

class ClientHandler():
    def __init__(self, stream):
        self.stream = stream
        self.stream._pyroBind()
        self.stream._pyroOneway.add("add_queue")
        self.running = True
        self.throttle = False
    
    def process_data(self, queue):
        try:
            while self.running:
                clusters, data = [],[]
                for idx in xrange(QUEUE_SIZE):
                    try:
                        item = queue.get_nowait()
                        clusters.append(item[0])
                        data.append(item[1])
                    except:
                        continue
                if len(clusters):
                    self.stream.add_queue(zip(clusters, data))
                """
                while self.stream.throttle_needed():
                    self.throttle = True
                    sleep(1)
                self.throttle = False
                """
            while not queue.empty():
                item = queue.get_nowait()
                clusters.append(item[0])
                data.append(item[1])
            if len(clusters):
                self.stream.add_queue(zip(clusters, data))
                clusters[:], data[:] = [], []
            return
        except KeyboardInterrupt:
            print "User aborted"
            sys.exit(-1)
