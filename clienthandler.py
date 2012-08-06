import sys
from time import sleep
QUEUE_SIZE = 4096

class ClientHandler():
    def __init__(self, stream):
        self.stream = stream
        self.running = True
        self.throttle = False
    
    def process_data(self, queue):
        try:
            clusters, data = [],[]
            while self.running:
                while not queue.empty():
                    item = queue.get()
                    clusters.append(item[0])
                    data.append(item[1])
                    if len(data) >= QUEUE_SIZE:
                        if self.stream.add_queue(clusters, data):
                            self.throttle = True
                            while self.stream.throttle_needed():
                                sleep(2)
                            self.throttle = False
                        del(clusters)
                        del(data)
                        clusters, data = [],[]
                if len(clusters):
                    if self.stream.add_queue(clusters, data):
                        self.throttle = True
                        while self.stream.throttle_needed():
                            sleep(2)
                        self.throttle = True
                    del(clusters)
                    del(data)
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
        