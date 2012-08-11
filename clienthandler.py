import sys
from time import sleep
QUEUE_SIZE = 4096

class ClientHandler():
    def __init__(self, stream):
        self.stream = stream
        self.running = True
    
    def process_data(self, queue):
        try:
            clusters, data = [],[]
            while self.running:
                item = queue.get()
                clusters.append(item[0])
                data.append(item[1])
                if len(data) >= QUEUE_SIZE:
                    self.stream.add_queue(clusters, data):
                    clusters, data = [],[]
            while not queue.empty():
                item = queue.get()
                clusters.append(item[0])
                data.append(item[1])
            self.stream.add_queue(clusters, data)
            sys.exit(0)
        except KeyboardInterrupt:
            print "User aborted"
            sys.exit(-1)
        