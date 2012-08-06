from pysolr import Solr

class TextIndexer:
    def __init__(self):
        self.solr = Solr(url='http://localhost:8983/solr')
        self.running = True

    def indexer_queue(self, queue):
        while self.running:
            target = queue.get()
            with open(target, 'rb') as fh:
                self.solr.extract(fh)
        while len(queue):
            target = queue.get()
            with open(target, 'rb') as fh:
                self.solr.extract(fh)
        return