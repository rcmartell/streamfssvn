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

class Stream_Client():
    def __init__(self):
        self.cluster_size = 0
        self.files = {}
        self.file_progress = {}
        if os.path.isdir('Incomplete'):
            os.rmdir('Incomplete')
        if os.path.isdir('Complete'):
            os.rmdir('Complete')
        os.mkdir('Incomplete')
        os.mkdir('Complete')
        os.chdir('Incomplete')
        self.magic = File_Magic()
        self.queue = collections.deque()
        self.other = []
        self.handles = {}
        self.filenames = []

    """
    Set by Image Server
    """
    def set_cluster_size(self, size):
        self.cluster_size = int(size)
    
    """
    Set by Image Server
    """
    def set_num_clusters(self, num):
        self.num_clusters = int(num)
        self.clustermap = [0] * int(num)
    
    """
    Setup necessary data structures to process entries received from Image Server.
    """
    def process_entries(self, entries):
        for entry in entries:
            # To try and prevent name collisions
            try:
                entry.name = "[" + entry.parent + "]" + entry.name
            except:
                pass
            # NTFS is not consistent about where it stores a file's data size...
            if entry.real_size == 0:
                if entry.data_size != 0 and entry.data_size != None:
                    self.files[entry.name] = [entry.data_size, entry.clusters]
                else:
                    # If no size data is present, resort to num of clusters * cluster size
                    # This is not the most reliable method, as it's common for the final cluster
                    # to be only partially filled.
                    self.files[entry.name] = [len(entry.clusters) * self.cluster_size, entry.clusters]
            else:
                self.files[entry.name] = [entry.real_size, entry.clusters]
            # List of all files that will be received from Image Server and their clusters numbers.
            self.filenames.append(entry.name)

    """
    Create a mapping of clusters to their respective files.
    """
    def setup_clustermap(self):
        for k,v in self.files.iteritems():
            for c in v[1]:
                self.clustermap[int(c)] = k

    """
    Create a dictionary containing the number of clusters each file is composed of.
    """
    def setup_file_progress(self):
        for file in self.files:
            file = intern(file)
            self.file_progress[file] = len(self.files[file][1])

    """
    Create a list of all the clusters this client will be receiving.
    """
    def list_clusters(self):
        self.clusters = []
        for k,v in self.files.iteritems():
            try:
                self.clusters.extend(v[1])
            except:
                self.clusters.append(v[1])
        return self.clusters

    """
    Method used by Image Server to transfer cluster/data to client.
    """
    def add_queue(self, cluster, data):
        self.queue.extend(zip(cluster, data))

    """
    Helper method to spawn write_data in a seperate thread.
    """
    def queue_writes(self):
        self.thread = threading.Thread(target=self.write_data)
        self.thread.start()
        return


    """
    Writes file data to disk.
    """
    def write_data(self):
        try:
            while True:
                # The queue is emtpy and all remaining files have been written to disk.
                if len(self.file_progress) == 0 and len(self.queue) == 0:
                    break
                # Waiting for server to fill queue.
                while len(self.queue) == 0:
                    time.sleep(0.005)
                # The filedb dictionary is a database which holds the mappings of the cluster/data
                # pairs pulled from the queue to their respective files. The dictionary shoulds a
                # limited number of file entries (the number of queue items we work on at one time) in
                # order to prevent excessive memory-overhead.
                filedb = {}
                # Work on 1000 entries at a time.
                for idx in range(1000):
                    # Queues empty again. This check is necessary since we can't always
                    # wait for a specific number of queue entries, as that may leave us
                    # with a partially filled queue at the end of the imaging process.
                    if len(self.queue) == 0:
                        break
                    # Grab the entry's cluster number and data
                    cluster, data = self.queue.popleft()
                    try:
                        # If the file exists in our dict, append the entry
                        filedb[self.clustermap[cluster]].append((cluster, data))
                    except:
                        # Else create a new entry.
                        filedb[self.clustermap[cluster]] = [(cluster, data)]
                # In order to minimize random-writes/seeks, we attempt to write all data entries of
                # a file obtained from the queue before moving on to another file. Due to file-system
                # fragmentation this can be tricky since not all of a file's clusters will be sequential
                # or even in ascending order.
                for file in filedb:
                    # Try opening the file in-case we have already written data to it. Otherwise create it.
                    try:
                        fh = open(file, 'r+b')
                    except:
                        fh = open(file, 'wb')
                    buff = []
                    # Create individual lists for clusters and data, but maintain their original indices to
                    # preserve the mappings between them.
                    clusters, data = zip(*files[file])
                    idx = 0
                    # Iterate through the list of clusters belonging to the current file.
                    while idx < len(clusters):
                        # Offset into file where the first data entry of the sequence belongs
                        seek = clusters[idx]
                        # Create a buffer of sequential data entries for the file.
                        buff.append(data[idx])
                        try:
                            while clusters[idx+1] == clusters[idx] + 1:
                                buff.append(data[idx+1])
                                idx += 1
                        except:
                            pass
                        # Seek to the offset where the initial data entry should be written.
                        fh.seek(self.files[file][1].index(seek) * self.cluster_size, os.SEEK_SET)
                        # Check to see if the last cluster is padded or not.
                        if fh.tell() + len("".join(buff)) > int(self.files[file][0]):
                            # If so, truncate the write to the correct length.
                            left = int(self.files[file][0] - fh.tell())
                            out = "".join(buff)
                            fh.write(out[:left])
                            fh.flush()
                        else:
                            fh.write("".join(buff))
                            fh.flush()
                        # Subtract the number of clusters written to the file from its total.
                        self.file_progress[file] -= len(buff)
                        buff = []
                        idx += 1
                    # All clusters pulled from the queue belonging to the current file have been written to disk.
                    fh.close()
                    # If the file's entry in self.file_progress is 0, then all clusters have been written to disk
                    # and the file is complete.
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
    uri = daemon.register(Stream_Client())
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
