#!/usr/bin/python
from mftparser import MFTParser
from time import ctime
from progressbar import ProgressBar, Percentage, Bar, ETA, FileTransferSpeed
from clienthandler import ClientHandler
import warnings, gc, sys, json
from multiprocessing import Queue, Process
warnings.filterwarnings("ignore")
import Pyro4.core

QUEUE_SIZE = 8192
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
        config = json.load(open('config.json'))
        for idx in range(len(config['Filetypes'])):
            self.types.extend(config['Filetypes'][idx].values()[0])

    def parse_fs_metadata(self, fstype = 'ntfs'):
        print 'Parsing filesystem metadata...',
        if fstype.lower() == 'ntfs':
            parser = MFTParser(self.src)
            self.cluster_size = parser.get_cluster_size()
            self.num_clusters = parser.get_num_clusters()
            #self.entries = filter(lambda x : x.name.split('.')[1].upper() in self.types, parser.main())
            self.entries = parser.main()
            self.mapping = [None] * self.num_clusters
        del(parser)
        print 'Done.'

    def setup_stream_listeners(self, servers):
        print 'Setting up stream listeners...',
        self.streams = []
        for idx in range(len(servers)):
            self.streams.append(Pyro4.core.Proxy("PYRONAME:%s" % servers[idx]))
            self.streams[idx]._pyroBind()
            self.streams[idx]._pyroOneway.add("add_queue")
            self.streams[idx].set_cluster_size(self.cluster_size)
            self.streams[idx].set_num_clusters(self.num_clusters)
            self.streams[idx].process_entries(self.entries[idx::len(servers)])
            for cluster in self.streams[idx].list_clusters():
                self.mapping[cluster] = idx
            self.streams[idx].clear_clusters()
        del(self.entries)
        gc.collect()
        print 'Done.'

    def image_drive(self):
        ifh = open(self.src, 'rb')
        self.finished = False
        handlers = []
        queues = [Queue() for idx in range(len(self.streams))]
        procs = []
        for stream in self.streams:
            stream.setup_clustermap()
            stream.setup_file_progress()
            stream.queue_writes()
            stream.queue_showStatus()
            handlers.append(ClientHandler(stream))
        for idx in range(len(handlers)):
            procs.append(Process(target=handlers[idx].process_data, args=(queues[idx],)).start())
        print 'Imaging drive...'
        pbar = ProgressBar(widgets = self.widgets, maxval = len(self.mapping) * self.cluster_size).start()
        count = len(self.mapping)
        for i in xrange(0, count, 4096):
            data = ifh.read(self.cluster_size * 4096)
            for idx in xrange(i, i + (len(data) / self.cluster_size)):
                target = self.mapping[idx]
                if target == None:
                    continue
                queues[target].put_nowait((idx, data[idx:idx + self.cluster_size]))
                if not idx % 100:
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
    server.setup_stream_listeners(sys.argv[3:])
    try:
        server.image_drive()
    except KeyboardInterrupt:
        sys.exit(-1)
    print "End Time: %s" % str(ctime().split(" ")[4])
if __name__ == "__main__":
    main()
