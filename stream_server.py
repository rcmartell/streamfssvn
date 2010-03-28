#!/usr/bin/python
import Pyro.core, Pyro.naming, Pyro.util
import sys, os, shutil
import threading
from time import ctime
from file_magic import *
from threading import Lock

try:
    import psyco
    psyco.full()
except:
    pass

class Stream_Server(Pyro.core.ObjBase):
    def __init__(self):
        Pyro.core.ObjBase.__init__(self)
        self.cluster_size = 0
        self.files = {}
        self.clustermap = {}
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

    def set_cluster_size(self, size):
        self.cluster_size = int(size)

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
                self.clustermap[c] = k
    

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
        self.clusters.sort()
    
    def write_data(self, clusters, _data_):
        idx = 0
        #self.rlock = threading.Lock()
        for cluster in clusters:
            data = _data_[idx:idx+self.cluster_size]
            idx += self.cluster_size
            #TODO: see which is faster
            file = self.clustermap.get(cluster)
            if file is None:
                continue
            #self.rlock.acquire()
            try:
                fh = open(file, 'rb+')
            except:
                fh = open(file, 'wb')
            fh.seek(self.cluster_size * self.files[file][1].index(cluster), os.SEEK_SET)
            if (fh.tell() + self.cluster_size) > int(self.files[file][0]):
                left = int(self.files[file][0]) - fh.tell()
                fh.write(data[:left])
            else:
                fh.write(data)
            fh.close()
            #self.rlock.release()
            self.file_progress[file] -= 1
            if not self.file_progress[file]:
                self.file_complete(file)
        return

    def file_complete(self, filename):
        del(self.files[filename])
        self.magic.process_file(filename)

def main():
    Pyro.core.initServer()
    ns = Pyro.naming.NameServerLocator().getNS()
    daemon = Pyro.core.Daemon()
    daemon.useNameServer(ns)
    uri = daemon.connect(Stream_Server(), sys.argv[1])
    print uri
    daemon.requestLoop()

if __name__ == "__main__":
    try:
        import psyco
        psyco.full()
    except:
        pass
    main()
