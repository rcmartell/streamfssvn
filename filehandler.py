from md5 import md5

class FileHandler():
    def __init__(self):
        self.running = True
        self.hashes = {}

    def handler_queue(self, queue):
        while self.running or not queue.empty():
            target = queue.get()
            self.hashes[target] = md5(open(target, 'rb').read()).hexdigest()
        return
