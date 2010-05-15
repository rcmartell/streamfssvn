#!/usr/bin/python
import Pyro.core, Pyro.naming, Pyro.util
import sys, os, shutil, time
import threading, socket, resource
from file_magic import File_Magic

resource.setrlimit(resource.RLIMIT_NOFILE, (1024,-1))

class Stream_Server():
    def __init__(self):
        self.cluster_size = 0
        self.files = {}
        self.file_progress = {}
        try:
            os.rmdir('Incomplete')
            os.rmdir('Complete')
        except:
            pass
        try:
            os.mkdir('Incomplete')
            os.mkdir('Complete')
        except:
            pass
        os.chdir('Incomplete')
        self.magic = File_Magic()
        self.handles = {}
        self.queue = []

    def set_cluster_size(self, size):
        self.cluster_size = int(size)

    def set_num_clusters(self, num):
        self.num_clusters = int(num)
        self.clustermap = [0] * int(num)
    
    def process_entries(self, entries):
        for entry in entries:
            try:
                entry.name = "[" + entry.parent + "]" + entry.name
            except:
                pass
            if entry.real_size == 0:
                if entry.data_size != 0:
                    self.files[intern(entry.name)] = [entry.data_size, entry.clusters]
                else:
                    self.files[intern(entry.name)] = [len(entry.clusters) * self.cluster_size, entry.clusters]
            else:
                self.files[intern(entry.name)] = [entry.real_size, entry.clusters]

    def setup_clustermap(self):
        for k,v in self.files.iteritems():
            for c in v[1]:
                self.clustermap[int(c)] = k
    
    def setup_file_progress(self):
        for file in self.files:
            file = intern(file)
            self.file_progress[file] = len(self.files[file][1])

    def list_clusters(self):
        self.clusters = []
        for k,v in self.files.iteritems():
            try:
                self.clusters.extend(v[1])
            except:
                self.clusters.append(v[1])
        return self.clusters
    
    def queue_writes(self):
        self.thread = threading.Thread(target=self.write_data)
        self.thread.start()
        return
    
    def add_queue(self, cluster, data):
        self.queue.extend(zip(cluster, data))
    
    def write_data(self):
        while True:
            while len(self.queue) == 0:
                time.sleep(0.00005)
            cluster, data = self.queue.pop()
            file = self.clustermap[cluster]
            if len(self.handles) == 1024:
                for handle in self.handles:
                    self.handles[handle].close()
                self.handles = {}
            if file not in self.handles:
                    self.handles[file] = open(file, 'wb')
            self.handles[file].seek(self.cluster_size * self.files[file][1].index(cluster), os.SEEK_SET)
            if (self.handles[file].tell() + self.cluster_size) > int(self.files[file][0]):
                left = int(self.files[file][0]) - self.handles[file].tell()
                self.handles[file].write(data[:left])
            else:
                self.handles[file].write(data)
            self.file_progress[file] -= 1
            if not self.file_progress[file]:
                self.handles[file].close()
                del self.handles[file]
                self.magic.process_file(file)

def main():
    daemon = Pyro.core.Daemon()
    uri = daemon.register(Stream_Server())
    print "Host: %s\t\tPort: %i\t\tName: %s" % (socket.gethostname(), uri.port, sys.argv[1])
    ns=Pyro.naming.locateNS()
    ns.register(sys.argv[1], uri)
    daemon.requestLoop()

if __name__ == "__main__":
    try:
        import psyco
        psyco.full()
    except:
        print "Psyco failed"
        pass
    main()
