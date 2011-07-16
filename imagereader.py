#!/usr/bin/python
from mftparser import MFTParser
from time import time, ctime
from progressbar import *
from threading import *
from collections import deque
import warnings, gc
warnings.filterwarnings("ignore")
import Pyro4.core, Pyro4.util, threading

QUEUE_SIZE = 1000

class ImageReader():
    def __init__(self, src=None, dest=None):
        self.cluster_size = 0
        self.src = src
        self.dest = dest
        self.entries = None
        self.widgets = ['Progress: ', Percentage(), ' ', Bar(),' ', ETA(), ' ', FileTransferSpeed()]

    def init_fs_metadata(self, fstype='ntfs'):
        print 'Parsing filesystem metadata'
        if fstype.lower() == 'ntfs':
            parser = MFTParser(self.src)
            self.cluster_size = parser.get_cluster_size()
            self.num_clusters = parser.get_num_clusters()
            self.entries = parser.main()
            self.mapping = [-1] * self.num_clusters
        del(parser)

    def setup_stream_listeners(self, servers):
        print 'Setting up stream listeners'
        self.streams = []
        for idx in range(len(servers)):
            self.streams.append(Pyro4.core.Proxy("PYRONAME:%s" % servers[idx]))
            self.streams[idx]._pyroBind()
            self.streams[idx].set_cluster_size(self.cluster_size)
            self.streams[idx].set_num_clusters(self.num_clusters)
            self.streams[idx].process_entries(self.entries[idx::len(servers)])
            for cluster in self.streams[idx].list_clusters():
                self.mapping[cluster] = idx
                #self.mapping[cluster] = self.streams[idx]
            self.streams[idx].clear_clusters()
        del(self.entries)
        gc.collect()
        
    def image_drive(self):
        self.lock = [threading.Lock() for idx in range(len(self.streams))]
        ifh = open(self.src, 'rb')
        ofh = open(self.dest, 'wb+')
        self.finished = False
        self.thread_queue = [[[],[]] for idx in range(len(self.streams))]
        threads = [Thread(target=self.threaded_queue, args=(idx,)) for idx in range(len(self.streams))]
        for stream in self.streams:
            stream.setup_clustermap()
            stream.setup_file_progress()
            stream.queue_writes()
            stream.queue_showStatus()
        for thread in threads:
            thread.start()
        #cluster_queue = dict([(server, []) for server in self.streams])
        #data_queue = dict([(server, []) for server in self.streams])
        #queue_count = 0
        print 'Imaging drive...'
        pbar = ProgressBar(widgets=self.widgets, maxval=len(self.mapping) * self.cluster_size).start()
        for idx in range(len(self.mapping)):
            target = self.mapping[idx]
            if target == -1:
                data = ifh.read(self.cluster_size)
                #ofh.write(data)
                pbar.update(idx * self.cluster_size)
                continue
            #if queue_count == QUEUE_SIZE:
            #    [server.add_queue(cluster_queue[server], data_queue[server]) for server in self.streams]
            #    del(cluster_queue)
            #    del(data_queue)
            #    cluster_queue = dict([(server, []) for server in self.streams])
            #    data_queue = dict([(server, []) for server in self.streams])
            #    queue_count = 0
            data = ifh.read(self.cluster_size)
            self.lock[target].acquire()
            self.thread_queue[target][0].append(idx)
            self.thread_queue[target][1].append(data)
            self.lock[target].release()
            #pbar.update(idx * self.cluster_size)
            pbar.update(idx * self.cluster_size)
            #cluster_queue[target].append(idx)
            #data_queue[target].append(data)
            #queue_count += 1
            #ofh.write(data)
        self.finished = True
        pbar.finish()
        ifh.close()
        ofh.close()
        
    def threaded_queue(self, idx):
        tid = idx
        while True:
            while len(self.thread_queue[tid][0]) < QUEUE_SIZE:
                time.sleep(0.005)
                if self.finished:
                    clusters = self.thread_queue[tid][0]
                    data = self.thread_queue[tid][1]
                    self.streams[tid].add_queue(clusters, data)
                    return
            self.lock[tid].acquire()
            ###
            clusters = self.thread_queue[tid][0]
            data = self.thread_queue[tid][1]
            self.streams[tid].add_queue(clusters, data)
            del(self.thread_queue[tid][:])
            self.thread_queue[tid] = [[],[]]
            #gc.collect()
            ###
            self.lock[tid].release()
    

def main():
    print "Starting Time: %s" % str(time.ctime())
    irdr = ImageReader(sys.argv[1], sys.argv[2])
    irdr.init_fs_metadata()
    irdr.setup_stream_listeners(sys.argv[3:])
    irdr.image_drive()
    print "End Time: %s" % str(time.ctime())
if __name__ == "__main__":
    try:
        import psyco
        psyco.full()
    except:
        pass
    main()
