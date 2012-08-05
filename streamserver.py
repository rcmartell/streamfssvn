#!/usr/bin/python
from mftparser import MFTParser
from time import ctime
from progressbar import ProgressBar, Percentage, Bar, ETA, FileTransferSpeed
from clienthandler import ClientHandler
import warnings, gc, sys
from xml.etree import ElementTree as tree
from multiprocessing import Queue, Process
warnings.filterwarnings("ignore")
import Pyro4.core

QUEUE_SIZE = 4096
Pyro4.config.ONEWAY_THREADED = True

class StreamServer():
    def __init__(self, src = None, dest = None):
        self.cluster_size = 0
        self.src = src
        self.dest = dest
        self.entries = None
        self.types = []
        self.widgets = ['Progress: ', Percentage(), ' ', Bar(), ' ', ETA(), ' ', FileTransferSpeed()]

    def get_types(self):
        with open('config.xml') as fh:
            config = tree.fromstring(fh.read())
        for elem in config.getchildren()[0].findall('type'):
            if elem.get('include') == 'true':
                with open(elem.text) as fh:
                    self.types.extend(fh.read().split())

    def parse_fs_metadata(self, fstype = 'ntfs'):
        print 'Parsing filesystem metadata...',
        sys.stdout.flush()
        if fstype.lower() == 'ntfs':
            parser = MFTParser(self.src)
            self.cluster_size = parser.get_cluster_size()
            self.num_clusters = parser.get_num_clusters()
            self.entries = filter(lambda x : x.name.split('.')[1].upper() in self.types, parser.main())
            self.mapping = [None] * self.num_clusters
        del(parser)
        print 'Done.'

    def setup_stream_listeners(self, clients):
        print 'Setting up stream listeners...',
        sys.stdout.flush()
        self.streams = []
        for idx in range(len(clients)):
            self.streams.append(Pyro4.core.Proxy("PYRONAME:%s" % clients[idx]))
            self.streams[idx]._pyroBind()
            self.streams[idx]._pyroOneway.add("add_queue")
            self.streams[idx].set_cluster_size(self.cluster_size)
            self.streams[idx].set_num_clusters(self.num_clusters)
            self.streams[idx].process_entries(self.entries[idx::len(clients)])
            for cluster in self.streams[idx].list_clusters():
                self.mapping[cluster] = idx
        del(self.entries)
        gc.collect()
        print 'Done.'

    def process_image(self):
        ifh = open(self.src, 'rb')
        self.finished = False
        handlers = []
        queues = [Queue() for idx in range(len(self.streams))]
        procs = []
        for stream in self.streams:
            stream.setup_clustermap()
            stream.setup_file_progress()
            stream.queue_writes()
            stream.queue_show_status()
            handlers.append(ClientHandler(stream))
        for idx in range(len(handlers)):
            procs.append(Process(target=handlers[idx].process_data, args=(queues[idx],self.finished)).start())
        pbar = ProgressBar(widgets = self.widgets, maxval = len(self.mapping) * self.cluster_size).start()
        for idx in xrange(len(self.mapping)):
            target = self.mapping[idx]
            if target == None:
                data = ifh.read(self.cluster_size)
                continue
            data = ifh.read(self.cluster_size)
            queues[target].put_nowait((idx, data))
            if not idx % 10000:
                pbar.update(idx * self.cluster_size)
        self.finished = True
        for handler in handlers:
            handler.running = False
        for proc in procs:
            proc.join()
        pbar.finish()
        ifh.close()

def main():
    print "Starting Time: %s" % str(ctime().split(" ")[4])
    server = StreamServer(sys.argv[1], sys.argv[2])
    server.get_types()
    server.parse_fs_metadata()
    ns = Pyro4.locateNS()
    clients = []
    for entry in ns.list():
        if entry != "Pyro.NameServer":
            clients.append(entry)
    server.setup_stream_listeners(clients)
    try:
        server.process_image()
    except KeyboardInterrupt:
        sys.exit(-1)
    print "End Time: %s" % str(ctime().split(" ")[4])
if __name__ == "__main__":
    main()
