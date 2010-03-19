#!/usr/bin/python
import Pyro.core, Pyro.naming
import sys, os, shutil
import random, pickle
from time import ctime
from file_magic import *
import mmap


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

    def print_test(self, msg):
        print msg

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
                    self.files[entry.name] = [entry.data_size, entry.clusters]
                else:
                    self.files[entry.name] = [len(entry.clusters) * self.cluster_size, entry.clusters]
            else:
                self.files[entry.name] = [entry.real_size, entry.clusters]

    def setup_clustermap(self):
        for k,v in self.files.iteritems():
            for c in v[1]:
                self.clustermap[c] = k

    def setup_file_progress(self):
        for file in self.files:
            self.file_progress[file] = len(self.files[file][1])

    def list_clusters(self):
        clusters = []
        for k,v in self.files.iteritems():
            try:
                clusters.extend(v[1])
            except:
                clusters.append(v[1])
        return clusters


    def get_data(self, clusters, data_):
        idx = 0
        for cluster in clusters:
            data = data_[idx:idx+self.cluster_size]
            idx += self.cluster_size
            if cluster in self.clustermap:
                file = self.clustermap[cluster]
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
                self.file_progress[file] -= 1
                if not self.file_progress[file]:
                    self.file_complete(file)

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
