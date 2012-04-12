#!/usr/bin/python
from mftparser import MFTParser
from time import ctime, sleep
from progressbar import ProgressBar, Percentage, Bar, ETA, FileTransferSpeed
from threading import Thread, Lock
import warnings, gc, sys, os
warnings.filterwarnings("ignore")
import Pyro4.core

QUEUE_SIZE = 8192
Pyro4.config.ONEWAY_THREADED=True

class ImageReader():
    def __init__(self, src=None, dest=None):
        self.cluster_size = 0
        self.src = src
        self.dest = dest
        self.entries = None
        self.widgets = ['Progress: ', Percentage(), ' ', Bar(), ' ', ETA(), ' ', FileTransferSpeed()]

    def init_fs_metadata(self, fstype='ntfs'):
        print 'Parsing filesystem metadata...',
        sys.stdout.flush()
        if fstype.lower() == 'ntfs':
            parser = MFTParser(self.src)
            self.cluster_size = parser.get_cluster_size()
            self.num_clusters = parser.get_num_clusters()
            self.entries = parser.main()
            self.mapping = [-1] * self.num_clusters
        del(parser)
        print 'Done.'
        sys.stdout.flush()

    def setup_stream_listeners(self, servers):
        print 'Setting up stream listeners...',
        sys.stdout.flush()
        self.streams = []
        for idx in range(len(servers)):
            self.streams.append(Pyro4.core.Proxy("PYRONAME:%s" % servers[idx]))
            self.streams[idx]._pyroBind()
            self.streams[idx]._pyroOneway.add("add_queue")
            self.streams[idx].set_cluster_size(self.cluster_size)
            self.streams[idx].set_num_clusters(self.num_clusters)
            serializer = Pyro4.core.util.Serializer()
            s = serializer.serialize(self.entries[idx::len(servers)])
            fh = open("/home/rob/entriesObjectSerialized", "wb")
            fh.write(s[0])
            fh.close()
            self.streams[idx].process_entries(self.entries[idx::len(servers)])
            for cluster in self.streams[idx].list_clusters():
                self.mapping[cluster] = idx
            self.streams[idx].clear_clusters()
        del(self.entries)
        gc.collect()
        print 'Done.'
        sys.stdout.flush()

    def image_drive(self):
        self.lock = [Lock() for idx in range(len(self.streams))]
        ifh = open(self.src, 'rb')
        #ofh = open(self.dest, 'wb+')
        self.finished = False
        self.thread_queue = [[[], []] for idx in range(len(self.streams))]
        #threads = [Process(target=self.threaded_queue, args=(idx,)) for idx in range(len(self.streams))]
        threads = [Thread(target=self.threaded_queue, args=(idx,)) for idx in range(len(self.streams))]
        for stream in self.streams:
            stream.setup_clustermap()
            stream.setup_file_progress()
            stream.queue_writes()
            stream.queue_showStatus()
        for thread in threads:
            thread.start()
        print 'Imaging drive...'
        sys.stdout.flush()
        pbar = ProgressBar(widgets=self.widgets, maxval=len(self.mapping) * self.cluster_size).start()
        for idx in xrange(len(self.mapping)):
            target = self.mapping[idx]
            if target == -1:
                ifh.read(self.cluster_size)
                #ofh.write(ifh.read(self.cluster_size))
                pbar.update(idx * self.cluster_size)
                continue
            data = ifh.read(self.cluster_size)
            self.lock[target].acquire()
            self.thread_queue[target][0].append(idx)
            self.thread_queue[target][1].append(data)
            self.lock[target].release()
            #ofh.write(data)
            pbar.update(idx * self.cluster_size)
        self.finished = True
        for thread in threads:
            thread.join()
        for idx in range(len(self.streams)):
            try:
                self.streams[idx].add_queue(self.thread_queue[idx][0], self.thread_queue[idx][1])
            except:
                print "Error sending data to client: %d" % idx
                pass
        pbar.finish()
        ifh.close()
        #ofh.close()

    def threaded_queue(self, idx):
        tid = idx
        while True:
            while len(self.thread_queue[tid][0]) < QUEUE_SIZE:
                sleep(1)
                if self.finished:
                    return
            self.lock[tid].acquire()
            clusters = self.thread_queue[tid][0]
            data = self.thread_queue[tid][1]
            del(self.thread_queue[tid][:])
            self.thread_queue[tid] = [[], []]
            if self.streams[tid].add_queue(clusters, data):
                while self.streams[tid].throttle_needed():
                    sleep(2)
            self.lock[tid].release()

def main():
    if sys.platform == "win32":
        os.system("cls")
    else:
        os.system("clear")
    print "Starting Time: %s" % str(ctime().split(" ")[3])
    reader = ImageReader(sys.argv[1], sys.argv[2])
    reader.init_fs_metadata()
    reader.setup_stream_listeners(sys.argv[3:])
    try:
        reader.image_drive()
    except KeyboardInterrupt:
        sys.exit(-1)
    print "End Time: %s" % str(ctime().split(" ")[3])
if __name__ == "__main__":
    main()
