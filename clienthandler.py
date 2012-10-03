import sys
from time import sleep
QUEUE_SIZE = 65536

class ClientHandler():
    def __init__(self, stream):
        self.stream = stream
        self.running = True
    
    def process_data(self, queue):
        try:
            clusters, data = [],[]
            while self.running:
                for idx in xrange(QUEUE_SIZE):
                    try:
                        item = queue.get_nowait()
                        clusters.append(item[0])
                        data.append(item[1])
                    except:
                        continue
                if len(clusters):
                    self.stream.add_queue(zip(clusters, data))
                    clusters[:], data[:] = [],[]
            while not queue.empty():
                item = queue.get_nowait()
                clusters.append(item[0])
                data.append(item[1])
            self.stream.add_queue(zip(clusters, data))
            sys.exit(0)
        except KeyboardInterrupt:
            print "User aborted"
            sys.exit(-1)
