import sys
from time import sleep
QUEUE_SIZE = 16384

class ClientHandler():
    def __init__(self, stream, lock, queue):
        self.stream = stream
        self.running = True
        self.lock = lock
        self.queue = queue
    
    def process_data(self):
        try:
            items = []
            while self.running:
                for idx in xrange(QUEUE_SIZE):
                    if len(self.queue) == 0:
                        continue
                    items.append(self.queue.popleft())
                if len(items):
                    if self.stream.throttle_needed():
                        self.lock.acquire()
                        while self.stream.throttle_needed():
                            sleep(1)
                        self.lock.release()
                    self.stream.add_queue(items)
                    items[:] = []
        except KeyboardInterrupt:
            print "User aborted"
            sys.exit(-1)
        
