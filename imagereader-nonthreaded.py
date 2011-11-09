#!/usr/bin/python
from __future__ import division
from mftparser import MFTParser
from time import time, ctime
from progressbar import *
from threading import *
from collections import deque
import warnings, gc
warnings.filterwarnings("ignore")
import Pyro4.core, Pyro4.util, threading
from math import ceil

QUEUE_SIZE = 1024

class ImageReader():
    def __init__(self, src=None, dest=None):
        self.cluster_size = 0
        self.src = src
        self.dest = dest
        self.entries = None
        self.widgets = ['Progress: ', Percentage(), ' ', Bar(marker=RotatingMarker()), ' ', ETA(), ' ', FileTransferSpeed()]

    def init_fs_metadata(self, fstype='ntfs'):
        print 'Parsing filesystem metadata...',
        if fstype.lower() == 'ntfs':
            parser = MFTParser(self.src)
            self.cluster_size = parser.get_cluster_size()
            self.num_clusters = parser.get_num_clusters()
            self.entries = parser.main()
            self.mapping = [-1] * self.num_clusters
        del(parser)
        print 'Done.'

    def setup_stream_listeners(self, servers):
        print 'Setting up stream listeners...',
        self.streams = []
        for idx in range(len(servers)):
            self.streams.append(Pyro4.core.Proxy("PYRONAME:%s" % servers[idx]))
            self.streams[idx]._pyroBind()
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
        ofh = open(self.dest, 'wb+')
        for stream in self.streams:
            stream.setup_clustermap()
            stream.setup_file_progress()
            stream.queue_writes()
            stream.queue_showStatus()
        count = 0
        data_queue = [0] * len(self.streams)
        for idx in range(len(self.streams)):
            data_queue[idx] = [[], []]
        print 'Imaging drive...'
        pbar = ProgressBar(widgets=self.widgets, maxval=len(self.mapping) * self.cluster_size).start()
        for idx in range(len(self.mapping)):
            target = self.mapping[idx]
            if target == -1:
                ofh.write(ifh.read(self.cluster_size))
                pbar.update(idx * self.cluster_size)
                continue
            data = ifh.read(self.cluster_size)
            if count == QUEUE_SIZE:
                [self.streams[idx].add_queue(data_queue[idx][0], data_queue[idx][1]) for idx in range(len(self.streams))]
                for idx in range(len(self.streams)):
                    del(data_queue[idx][:])
                    data_queue[idx] = [[], []]
                count = 0
                pbar.update(idx * self.cluster_size)
                continue
            data_queue[self.mapping[idx]][0].append(idx)
            data_queue[self.mapping[idx]][1].append(data)
            ofh.write(data)
            pbar.update(idx * self.cluster_size)
            count += 1
        try:
            [self.streams[idx].add_queue(data_queue[idx][0], data_queue[idx][1]) for idx in range(len(self.streams))]
        except:
            pass
        pbar.finish()
        ifh.close()
        ofh.close()

def main():
    print "Starting Time: %s" % str(time.ctime())
    irdr = ImageReader(sys.argv[1], sys.argv[2])
    irdr.init_fs_metadata()
    irdr.setup_stream_listeners(sys.argv[3:])
    irdr.image_drive()
    print "End Time: %s" % str(time.ctime())
if __name__ == "__main__":
    main()