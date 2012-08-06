from pysolr import Solr

class TextIndexer:
    def __init__(self):
        self.solr = Solr(url='http://localhost:8983/solr')
        self.running = True

    def indexer_queue(self, queue):
        while self.running:
            target = queue.get()
            self.solr.extract(target)
        while len(queue):
            target = queue.get()
            self.solr.extract(target)
        return