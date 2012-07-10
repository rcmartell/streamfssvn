from time import sleep
QUEUE_SIZE = 8192

class ClientHandler():
    def __init__(self, stream):
        self.stream = stream
        self.running = True
    
    def process_data(self, queue):
        clusters, data = [],[]
        while self.running:
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
            if self.stream.add_queue(clusters, data):
                while self.stream.throttle_needed():
                    sleep(2)
            del(clusters)
            del(data)
            clusters, data = [],[]
        while not queue.empty():
            item = queue.get()
            clusters.append(item[0])
            data.append(item[1])
        self.stream.add_queue(clusters, data)
        return
        
            