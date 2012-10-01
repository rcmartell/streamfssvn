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
                try:
                    item = queue.get_nowait()
                except:
                    continue
                clusters.append(item[0])
                data.append(item[1])
                if len(clusters) >= QUEUE_SIZE:
                    self.stream.add_queue(zip(clusters, data))
                    clusters[:], data[:] = [],[]
            while not queue.empty():
                item = queue.get(block=True)
                clusters.append(item[0])
                data.append(item[1])
            self.stream.add_queue(clusters, data)
            sys.exit(0)
        except KeyboardInterrupt:
            print "User aborted"
            sys.exit(-1)
