#!/usr/bin/python
from mftparser import MFTParser
from time import ctime, sleep
from progressbar import ProgressBar, Percentage, Bar, ETA, FileTransferSpeed
from threading import Thread, Lock
import warnings, gc, sys, os
from xml.etree import ElementTree as tree
from multiprocessing import Process, Queue
from clienthandler import ClientHandler
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
         with open('config/config.xml') as fh:
            config = tree.fromstring(fh.read())
         for elem in config.getchildren()[0].findall('type'):
            if elem.get('include') == 'true':
                with open('config' + os.path.sep + elem.text) as fh:
                    self.types.extend(fh.read().split())

    def parse_fs_metadata(self, fstype = 'ntfs'):
        print 'Parsing filesystem metadata...',
        sys.stdout.flush()
        if fstype.lower() == 'ntfs':
            parser = MFTParser(self.src)
            self.cluster_size = parser.get_cluster_size()
            self.num_clusters = parser.get_num_clusters()
            #self.entries = filter(lambda x : x.name.split('.')[1].upper() in self.types, parser.main())
            self.entries = parser.main()
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
        self.lock = [Lock() for idx in range(len(self.streams))]
        ifh = open(self.src, 'rb')
        #ofh = open(self.dest, 'wb+')
        self.finished = False
        self.queues = [Queue(maxsize=524288) for idx in range(len(self.streams))]
        self.handlers = [ClientHandler(stream) for stream in self.streams]
        self.procs = [Process(target=self.handlers[idx].process_data, args=(self.queues[idx],)) for idx in range(len(self.queues))]
        #self.thread_queue = [[[], []] for idx in range(len(self.streams))]
        #threads = [Thread(target = self.threaded_queue, args = (idx,)) for idx in range(len(self.streams))]
        for stream in self.streams:
            stream.setup_clustermap()
            stream.setup_file_progress()
            stream.queue_writes()
            stream.queue_show_status()
        #for thread in threads:
	    #thread.setDaemon(True)
        #    thread.start()
        for proc in self.procs:
            proc.start()
        pbar = ProgressBar(widgets = self.widgets, maxval = len(self.mapping) * self.cluster_size).start()
        for idx in xrange(len(self.mapping)):
            target = self.mapping[idx]
            if target == None:
                data = ifh.read(self.cluster_size)
                #ofh.write(data)
                continue
            data = ifh.read(self.cluster_size)
            self.queues[target].put((idx, data), block=True)
            #self.lock[target].acquire()
            #self.thread_queue[target][0].append(idx)
            #self.thread_queue[target][1].append(data)
            #self.lock[target].release()
            #ofh.write(data)
            if not idx % 10000:
                pbar.update(idx * self.cluster_size)
        self.finished = True
        for handler in self.handlers:
            handler.running = False
        #for thread in threads:
        #    thread.join()
        pbar.finish()
        ifh.close()
        print 'Done.'
        #ofh.close()

    def threaded_queue(self, idx):
        tid = idx
        while True:
            while len(self.thread_queue[tid][0]) < QUEUE_SIZE:
                sleep(1)
                if self.finished:
                    clusters = self.thread_queue[tid][0]
                    data = self.thread_queue[tid][1]
                    if len(clusters):
                        self.streams[tid].add_queue(clusters, data)
                    return
            self.lock[tid].acquire()
            clusters = self.thread_queue[tid][0]
            data = self.thread_queue[tid][1]
            self.thread_queue[tid][:] = [[],[]]
            self.lock[tid].release()
            self.streams[tid].add_queue(clusters, data)
            #if self.streams[tid].throttle_needed():
            #    self.lock[tid].acquire()
            #    while self.streams[tid].throttle_needed():
            #        sleep(2)
            #    self.lock[tid].release()

def main():
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

if __name__ == "__main__":
    main()
