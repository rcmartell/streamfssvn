import sys
from time import sleep
QUEUE_SIZE = 16384

class ClientHandler():
    def __init__(self, stream):
        self.stream = stream
        self.running = True
    
    def process_data(self, queue):
        try:
            clusters, data = [],[]
            while self.running:
                item = queue.get(block=True)
                clusters.append(item[0])
                data.append(item[1])
                if len(clusters) >= QUEUE_SIZE:
                    while self.stream.get_queue_size() + len(clusters) >= 524288:
                        sleep(2)
                    self.stream.add_queue(clusters, data)
                    clusters, data = [],[]
            while not queue.empty():
                item = queue.get(block=True)
                clusters.append(item[0])
                data.append(item[1])
            self.stream.add_queue(clusters, data)
            sys.exit(0)
        except KeyboardInterrupt:
            print "User aborted"
            sys.exit(-1)
