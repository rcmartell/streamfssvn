#!/usr/bin/python
from mftparser import MFTParser
from time import ctime, sleep
from progressbar import ProgressBar, Percentage, Bar, ETA, FileTransferSpeed
from threading import Thread, Lock
import warnings, gc, sys, os
from xml.etree import ElementTree as tree
from collections import deque
from Queue import Queue
from clienthandler import ClientHandler
warnings.filterwarnings("ignore")
import Pyro4.core

QUEUE_SIZE = 16384 
Pyro4.config.ONEWAY_THREADED = True

class StreamServer():
    def __init__(self, src = None, dest = None):
        self.cluster_size = 0
        self.src = src
        self.dest = dest
        self.entries = None
        self.types = []
        self.widgets = ['Progress: ', Percentage(), ' ', Bar(), ' ', ETA(), ' ', FileTransferSpeed()]

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
        read_ifh = ifh.read
        #ofh = open(self.dest, 'wb+')
        self.finished = False
        self.handler_queues = [deque() for idx in range(len(self.streams))]
        self.handlers = []
        self.handler_procs = []
        for idx in range(len(self.lock)):
            self.handlers.append(ClientHandler(self.streams[idx], self.lock[idx]))
            self.handler_procs.append(target=self.handlers[idx].process_data, args=self.handler_queues[idx])
        for stream in self.streams:
            stream.setup_clustermap()
            stream.setup_file_progress()
            stream.queue_writes()
            stream.queue_show_status()
        for proc in self.handler_procs:
            proc.start()
        pbar = ProgressBar(widgets = self.widgets, maxval = len(self.mapping) * self.cluster_size).start()
        for idx in xrange(len(self.mapping)):
            target = self.mapping[idx]
            data = read_ifh(self.cluster_size)
            if target == None:                
                continue
	        self.lock[target].acquire()
            self.handler_queues.append((idx, data))
            self.lock[target].release()
            if not idx % 25000:
                pbar.update(idx * self.cluster_size)
        for handler in self.handlers
            handler.running = False
        pbar.finish()
        ifh.close()
        print 'Done.'
        #ofh.close()
    
    """   
    def threaded_queue(self, idx):
        tid = idx
        lock = self.lock[tid]
	    stream = self.streams[tid]
	    while True:
            while len(self.thread_queue[tid]) < QUEUE_SIZE:
                sleep(0.25)
                if self.finished:
                    if len(self.thread_queue[tid]):
                        stream.add_queue(self.thread_queue[tid])
                    return
            lock.acquire()
            items = list(self.thread_queue[tid])
            self.thread_queue[tid].clear()
            lock.release()
            stream.add_queue(items)
            if stream.throttle_needed():
                lock.acquire()
                while self.streams[tid].throttle_needed():
                    sleep(1)
                lock.release()

    def write_image(self, ofh):
        while not self.finished or not self.writer_queue.empty():
            data = self.writer_queue.get()
            ofh.write(data)
        ofh.close()
    """            

def main():
    server = StreamServer(sys.argv[1], sys.argv[2])
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
