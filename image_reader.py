#!/usr/bin/python
from mft_parser import MFT_Parser
from time import time, ctime
from progressbar import *
from stream_server import Stream_Server
import Pyro.core, Pyro.util, threading

class Image_Reader():
    def __init__(self, src=None, dest=None):
        self.cluster_size = 0
        self.src = src
        self.dest = dest
        self.entries = None
        self.widgets = ['Progress: ', Percentage(), ' ', Bar(),' ', ETA(), ' ', FileTransferSpeed()]
        
    def init_fs_metadata(self, imgfile):
        print 'Parsing filesystem metadata'
        parser = MFT_Parser(imgfile)
        self.cluster_size = parser.get_cluster_size()
        self.img_size = parser.get_img_size()
        self.entries = parser.main()
        self.mapping = [0] * int(self.img_size)
        parser = None

    def setup_stream_listeners(self, servers):
        print 'Setting up stream servers'
        self.streams = []
        for idx in range(len(servers)):
            files = [entry for entry in self.entries[idx: len(self.entries): len(servers)]]
            self.streams.append(Pyro.core.Proxy("PYRONAME:%s" % servers[idx]))
            self.streams[-1]._pyroBind()
            self.streams[-1].set_cluster_size(self.cluster_size)
            self.streams[-1].set_num_clusters(self.img_size)
            self.streams[-1].process_entries(files)
            clusters = self.streams[-1].list_clusters()
            for cluster in clusters:
                self.mapping[cluster] = self.streams[-1]
        self.entries = []
        files = []

    def image_drive(self):
        self.count = int(self.img_size)
        ifh = open(self.src, 'rb')
        ofh = open(self.dest, 'wb+')
        for s in self.streams:
            s.setup_clustermap()
            s.setup_file_progress()
            s.queue_writes()
        stream_queue = {}
        queue_count = 0
        for stream in self.streams:
            stream_queue[stream] = []
        print 'Imaging drive...'
        pbar = ProgressBar(widgets=self.widgets, maxval=len(self.mapping) * self.cluster_size).start()
        for idx in range(len(self.mapping)):
            if self.mapping[idx] == 0:
                data = ifh.read(self.cluster_size)
                #ofh.write(data)
                pbar.update(idx * self.cluster_size)
                continue
            if queue_count == 1000:
                for server in stream_queue:
                    i, d = [], []
                    [(i.append(stream_queue[server][c][0]), d.append(stream_queue[server][c][1])) for c in range(len(stream_queue[server]))]
                    server.add_queue(i, d)
                for stream in self.streams:
                    stream_queue[stream] = []
                queue_count = 0
            data = ifh.read(self.cluster_size)
            queue_count += 1
            #self.mapping[idx].add_queue(idx, data)
            stream_queue[self.mapping[idx]].append((idx, data))
            #ofh.write(data)
            pbar.update(idx * self.cluster_size)
        pbar.finish()
        ifh.close()
        ofh.close()

def main():
    irdr = Image_Reader(src=sys.argv[1], dest=sys.argv[2])
    irdr.init_fs_metadata(imgfile=sys.argv[1])
    irdr.setup_stream_listeners(sys.argv[3:])
    irdr.image_drive()

if __name__ == "__main__":
    try:
        import psyco
        psyco.full()
    except:
        print "Psyco failed"
        pass
    main()
