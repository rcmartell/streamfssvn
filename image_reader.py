#!/usr/bin/python
from mft_parser import MFT_Parser
from time import time, ctime
from progressbar import *
from stream_server import Stream_Server
import Pyro.core, Pyro.util, threading
from threading import Thread

    
class Image_Reader():
    def __init__(self, src=None, dest=None):
        self.cluster_size = 0
        self.src = src
        self.dest = dest
        self.entries = None
        self.widgets = ['Progress: ', Percentage(), ' ', Bar(marker=RotatingMarker()),' ', ETA(), ' ', FileTransferSpeed()]
        
    def init_fs_metadata(self, img):
        print 'Parsing filesystem metadata'
        parser = MFT_Parser(img)
        self.cluster_size = parser.get_cluster_size()
        self.img_size = parser.get_img_size()
        self.entries = parser.main()
        parser = None

    def setup_stream_listeners(self, servers):
        print 'Setting up stream listeners'
        self.streams = []
        for idx in range(len(servers)):
            files = [entry for entry in self.entries[idx: len(self.entries): len(servers)]]
            self.streams.append(Pyro.core.getProxyForURI("PYROLOC://%s" % servers[idx]))
            self.streams[-1].set_cluster_size(self.cluster_size)
            self.streams[-1].process_entries(files)
        self.entries = []
        files = []

    def image_drive(self):
        self.count = int(self.img_size)
        ifh = open(self.src, 'rb')
        ofh = open(self.dest, 'wb+')
        cluster = 0
        bytes_copied = 0
        for s in self.streams:
            s.setup_clustermap()
            s.setup_file_progress()
            s.list_clusters()
        print 'Imaging drive...'
        pbar = ProgressBar(widgets=self.widgets, maxval=self.count * self.cluster_size).start()
        while self.count:
            t1 = time.time()
            if self.count >= 10240:
                data = ifh.read(10240 * self.cluster_size)
                try:
                    cluster_range = range(cluster, cluster+10240)
                    for s in self.streams:
                        s.get_data(cluster_range, data)
                except Exception, x:
                    print ''.join(Pyro.util.getPyroTraceback(x))
                #ofh.write(data)
                bytes_copied += 10240 * self.cluster_size
                self.count -= 10240
                cluster += 10240
            else:
                data = ifh.read(self.count * self.cluster_size)
                cluster_range = range(cluster, cluster + self.count)
                for s in self.streams:
                    try:
                        s.get_data(cluster_range, data)
                    except Exception, x:
                        print ''.join(Pyro.util.getPyroTraceback(x))
                #ofh.write(data)
                bytes_copied += self.count * self.cluster_size
                cluster += self.count
                break
            t2 = time.time()
            print "Avg. MBs: %0.3f" % (40.0 / (t2 - t1)) 
            pbar.update(bytes_copied)
        pbar.finish()
        ifh.close()
        ofh.close()
        print "Copied %i bytes" % bytes_copied


if __name__ == "__main__":
    try:
        import psyco
        psyco.full()
    except:
        pass
    irdr = Image_Reader(src=sys.argv[1], dest=sys.argv[2])
    print ctime()
    irdr.init_fs_metadata(img=sys.argv[1])
    print ctime()
    irdr.setup_stream_listeners(sys.argv[3:])
    print ctime()
    irdr.image_drive()
    print ctime()
