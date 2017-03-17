from pysolr import Solr
import threading

class TextIndexer:
    def __init__(self):
        self.running = True

    def init_threads(self, queue):
        threads = [threading.Thread(target=self.index_text, args=(queue,)) for i in range(12)]
        for thread in threads:
            thread.setDaemon(True)
            thread.start()
        for thread in threads:
            thread.join()

    def index_text(self, queue):
        solr = Solr(url='http://localhost:8983/solr')
        while self.running or not queue.empty():
            target = queue.get()
            fh = open(target, 'rb')
            solr.extract(fh)
            fh.close()
