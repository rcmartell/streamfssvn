#!/usr/bin/python
from mft_parser import *
from time import ctime
from progressbar import *
from stream_server import *
import Pyro.core, threading


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
        files = []
        self.streams = []
        for idx in range(len(servers)):
            files = [entry for entry in self.entries[idx: len(self.entries): len(servers)]]
            self.streams.append(Pyro.core.getProxyForURI("PYRONAME://%s" % servers[idx]))
            self.streams[-1].set_cluster_size(self.cluster_size)
            self.streams[-1].process_entries(self.entries)
        self.entries = []

    def image_drive(self):
        print 'Imaging drive...'
        self.clusters = []
        for s in self.streams:
            s.setup_clustermap()
            s.setup_file_progress()
            try:
                self.clusters.extend(s.list_clusters())
            except:
                self.clusters.append(s.list_clusters())
        self.count = int(self.img_size)
        ifh = open(self.src, 'rb')
        ofh = open(self.dest, 'wb+')
        cluster = 0
        bytes_copied = 0
        pbar = ProgressBar(widgets=self.widgets, maxval=self.count * self.cluster_size).start()
        while self.count:
            if self.count >= 100:
                data = ifh.read(100 * self.cluster_size)
                cluster_range = range(cluster, cluster+100)
                threads = []
                for stream in self.streams:
                    threads.append(threading.Thread(target=stream.get_data, args=(cluster_range, data)))
                    threads[-1].start()
                #for s in self.streams:
                #    s.get_data(cluster_range, data)
                #ofh.write(data)
                for thread in threads:
                    thread.join()
                bytes_copied += 100 * self.cluster_size
                self.count -= 100
                cluster += 100
            else:
                data = ifh.read(self.count * self.cluster_size)
                cluster_range = range(cluster, cluster + self.count)
                for s in self.streams:
                    s.get_data(cluster_range, data)
                #ofh.write(data)
                bytes_copied += self.count * self.cluster_size
                cluster += self.count
                break
            pbar.update(bytes_copied)
        pbar.finish()
        ifh.close()
        ofh.close()
        print "Copied %i bytes" % bytes_copied


if __name__ == "__main__":
    import psyco
    psyco.full()
    irdr = Image_Reader(src=sys.argv[1], dest=sys.argv[2])
    print ctime()
    irdr.init_fs_metadata(img=sys.argv[1])
    print ctime()
    irdr.setup_stream_listeners(sys.argv[3:])
    print ctime()
    irdr.image_drive()
    print ctime()
