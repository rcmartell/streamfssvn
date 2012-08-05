import sys
from time import sleep
QUEUE_SIZE = 8192

class ClientHandler():
    def __init__(self, stream):
        self.stream = stream
    
    def process_data(self, queue, finished):
        try:
            clusters, data = [],[]
            while not finished:
                while not queue.empty():
                    item = queue.get()
                    clusters.append(item[0])
                    data.append(item[1])
                    if len(data) >= QUEUE_SIZE:
                        if self.stream.add_queue(clusters, data):
                            while self.stream.throttle_needed():
                                sleep(2)
                        del(clusters)
                        del(data)
                        clusters, data = [],[]
                if len(clusters):
                    if self.stream.add_queue(clusters, data):
                        while self.stream.throttle_needed():
                            sleep(2)
                    del(clusters)
                    del(data)
                    clusters, data = [],[]
                sleep(2)
            while not queue.empty():
                item = queue.get()
                clusters.append(item[0])
                data.append(item[1])
            self.stream.add_queue(clusters, data)
            sys.exit(0)
        except KeyboardInterrupt:
            print "User aborted"
            sys.exit(-1)
        