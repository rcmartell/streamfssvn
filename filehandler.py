import sys
from md5 import md5

class FileHandler():
    def __init__(self):
        self.running = True
        self.hashes = {}

    def handler_queue(self, queue):
        getitem = queue.get_nowait
        qempty = queue.empty
        while self.running or not qempty():
            try:
                target = getitem()
                self.hashes[target] = md5(open(target, 'rb').read()).hexdigest()
            except:
                pass
        fh = open("filehashes.txt", "wb")
        for k,v in self.hashes.iteritems:
            write("%s : %s" % (k,v))
        fh.close()
        return
