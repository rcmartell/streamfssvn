#!/usr/bin/python
from mft_parser import MFT_Parser
from time import time, ctime, sleep
from progressbar import *
from stream_client import Stream_Client
import Pyro.core, Pyro.util, threading


class Image_Server():
    def __init__(self, src=None, dest=None):
        self.cluster_size = 0
        self.src = src
        self.dest = dest
        self.entries = None
        self.widgets = ['Progress: ', Percentage(), ' ', Bar(marker=RotatingMarker()),' ', ETA(), ' ', FileTransferSpeed()]

    def init_fs_metadata(self, img):
        self.widgets = ['Progress: ', Percentage(), ' ', Bar(),' ', ETA(), ' ', FileTransferSpeed()]

    def init_fs_metadata(self, imgfile):
        print 'Parsing filesystem metadata'
        parser = MFT_Parser(imgfile)
        self.cluster_size = parser.get_cluster_size()
        print "Filesystem Cluster Size: %d" % self.cluster_size
        self.img_size = parser.get_img_size()
        print "Filesystem size: %d" % (self.img_size * self.cluster_size)
        self.entries = parser.main()
        print "Number of Files: %d" % len(self.entries)
        self.mapping = [0] * int(self.img_size)
        parser = None

    def setup_stream_listeners(self, servers):
        print 'Setting up stream servers'
        self.streams = []
        entry_count = len(self.entries)
        remainder = entry_count % len(servers)
        server_idx = 0
        for server in servers:
            self.streams.append(Pyro.core.Proxy("PYRONAME:%s" % server))
            self.streams[-1]._pyroBind()
            self.streams[-1].set_cluster_size(self.cluster_size)
            self.streams[-1].set_num_clusters(self.img_size)
            server_entries = [self.entries[x] for x in range(server_idx, len(self.entries), len(servers))]
            if server_idx == len(servers) - 1 and remainder:
                rest = len(self.entries) - extra - 1
                server_entries.append(self.entries[rest:])
            self.streams[-1].process_entries(server_entries)
            clusters = self.streams[-1].list_clusters()
            for cluster in clusters:
                self.mapping[cluster] = self.streams[-1]
            server_idx += 1
        self.entries = []
        files = []

    def image_drive(self):
        ifh = open(self.src, 'rb')
        #ofh = open(self.dest, 'wb+')
        for s in self.streams:
            s.setup_clustermap()
            s.setup_file_progress()
            s.queue_writes()
        cluster_queue = {}
        data_queue = {}
        qcount = 0
        for stream in self.streams:
            cluster_queue[stream] = []
            data_queue[stream] = []
        print 'Imaging drive...'
        #pbar = ProgressBar(widgets=self.widgets, maxval=len(self.mapping) * self.cluster_size).start()
        for idx in range(len(self.mapping)):
            if self.mapping[idx] == 0:
                data = ifh.read(self.cluster_size)
                #ofh.write(data)
                #pbar.update(idx * self.cluster_size)
                continue
            data = ifh.read(self.cluster_size)
            qcount += 1
            cluster_queue[self.mapping[idx]].append(idx)
            data_queue[self.mapping[idx]].append(data)
            if qcount == 1000:
                [server.add_queue(cluster_queue[server], data_queue[server]) for server in self.streams]
                for stream in self.streams:
                    cluster_queue[stream] = []
                    data_queue[stream] = []
                qcount = 0
        [server.add_queue(cluster_queue[server], data_queue[server]) for server in self.streams]
            #ofh.write(data)
            #pbar.update(idx * self.cluster_size)
       #pbar.finish()
        ifh.close()
        #ofh.close()

def main():
    irdr = Image_Server(src=sys.argv[1])
    irdr.init_fs_metadata(imgfile=sys.argv[1])
    irdr.setup_stream_listeners(sys.argv[2:])
    irdr.image_drive()

if __name__ == "__main__":
    try:
        import psyco
        psyco.full()
    except:
        pass
    main()
