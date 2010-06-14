#!/usr/bin/python
import Pyro.core, Pyro.naming, Pyro.util
import sys, os, time
import threading, socket, collections, cProfile
import array
from array import array
from file_magic import File_Magic

try:
    import resource
    resource.setrlimit(resource.RLIMIT_NOFILE, (1024,-1))
    MAX_HANDLES = 1024
except:
    MAX_HANDLES = 9999

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
        self.queue = collections.deque()
        self.other = []
        self.handles = {}
        self.filenames = []

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
            self.filenames.append(entry.name)

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


    def add_queue(self, cluster, data):
        self.queue.extend(zip(cluster, data))

    def queue_writes(self):
        self.thread = threading.Thread(target=self.write_data)
        self.thread.start()
        return

    def init_file_handler(self):
        self.thread = threading.Thread(target=self.setup_file_buffers)
        self.thread.start()
        return

    def setup_file_buffers(self):
        print 'Setup file buffers'
        count = 0
        while len(self.filenames) > 0:
            print 'Filenames left: %i' % len(self.filenames)
            self.fbuffer = {}
            for file in self.filenames[:50]:
                count += 1
                try:
                    self.fbuffer[file] = array('c', 'O' * int(self.files[file][0]))
                except:
                    continue
            for data in self.other:
                file = self.clustermap[item[0]]
                if file in self.fbuffer:
                    start = self.cluster_size * self.files[file][1].index(data[0])
                    end = start + self.cluster_size
                    self.fbuffer[file][start:end] = array('c', data[1])
                    self.file_progress[file] -= 1
            self.write_to_buffers()
            del self.filenames[:50]

    def write_to_buffers(self):
        print 'Write to buffers'
        threads = []
        file_buffer = []
        while True:
            if len(self.file_progress) == 0:
                break
            while len(self.queue) == 0:
                time.sleep(0.0005)
            cluster, data = self.queue.popleft()
            file = self.clustermap[cluster]

            if file not in self.fbuffer:
                self.other.append((cluster, data))
                continue
            start = self.cluster_size * self.files[file][1].index(cluster)
            end = start + self.cluster_size
            self.fbuffer[file][start:end] = array('c', data)
            self.file_progress[file] -= 1
            if not self.file_progress[file]:
                del self.file_progress[file]
                threads.append(threading.Thread(target=self.write_to_disk, args=(file,)))
                threads[-1].start()
        for thread in threads:
            print "%s waiting on join" % thread
            thread.join()
            print "%s joined" % thread

    def write_to_disk(self, file):
        print 'Writing %s to disk' % file
        fh = open(file, 'wb')
        self.fbuffer[file].tofile(fh)
        self.magic.process_file(file)
        return

    def write_data(self):
        try:
            while True:
                if len(self.file_progress) == 0:
                    break
                while len(self.queue) == 0:
                    time.sleep(0.005)
                files = {}
                for idx in range(1000):
                    cluster, data = self.queue.popleft()
                    try:
                        files[self.clustermap[cluster]].append((cluster, data))
                    except:
                        files[self.clustermap[cluster]] = [(cluster, data)]
                for file in files:
                    try:
                        fh = open(file, 'r+b')
                    except:
                        fh = open(file, 'wb')
                    buff = []
                    clusters, data = zip(*files[file])
                    idx = 0
                    while idx < len(clusters):
                        seek = clusters[idx]
                        buff.append(data[idx])
                        try:
                            while clusters[idx+1] == clusters[idx] + 1:
                                buff.append(data[idx+1])
                                idx += 1
                        except:
                            pass
                        fh.seek(self.files[file][1].index(seek) * self.cluster_size, os.SEEK_SET)
                        if fh.tell() + len("".join(buff)) > int(self.files[file][0]):
                            left = int(self.files[file][0] - fh.tell())
                            out = "".join(buff)
                            fh.write(out[:left])
                            fh.flush()
                        else:
                            fh.write("".join(buff))
                            fh.flush()
                        self.file_progress[file] -= len(buff)
                        buff = []
                        idx += 1
                    fh.close()
                    if not self.file_progress[file]:
                        del self.files[file]
                        del self.file_progress[file]
                        self.magic.process_file(file)
        except KeyboardInterrupt:
            print 'User cancelled execution...'



                #cluster, data = self.queue.popleft()
                #file = self.clustermap[cluster]
                #if len(self.handles) == MAX_HANDLES:
                #    for handle in self.handles:
                #        self.handles[handle].close()
                #    self.handles = {}
                #if file not in self.handles:
                #        self.handles[file] = open(file, 'wb')
                #self.handles[file].seek(self.cluster_size * self.files[file][1].index(cluster), os.SEEK_SET)
                #if (self.handles[file].tell() + self.cluster_size) > int(self.files[file][0]):



#                    left = int(self.files[file][0]) - self.handles[file].tell()
#                    self.handles[file].write(data[:left])
#                else:
#                    self.handles[file].write(data)
#                self.file_progress[file] -= 1
#                if not self.file_progress[file]:
#                    self.handles[file].close()
#                    del self.handles[file]
#                    del self.file_progress[file]
#                    self.magic.process_file(file)
#        except KeyboardInterrupt:
#            print 'User cancelled execution...'


def main():
    daemon = Pyro.core.Daemon()
    uri = daemon.register(Stream_Server())
    print "Host: %s\t\tPort: %i\t\tName: %s" % (socket.gethostname(), uri.port, sys.argv[1])
    ns=Pyro.naming.locateNS()
    ns.register(sys.argv[1], uri)
    try:
        daemon.requestLoop()
    except KeyboardInterrupt:
        print 'User aborted'
        ns.remove(name=sys.argv[1])
        daemon.shutdown()

if __name__ == "__main__":
    try:
        import psyco
        psyco.full()
    except:
        pass
        #print "Psyco failed"
    main()
