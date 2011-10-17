#!/usr/bin/python
import sys, os, time, shutil
import threading, socket, collections, gc
from filemagic import FileMagic
import warnings, psutil
warnings.filterwarnings("ignore")
import Pyro4.core, Pyro4.naming, Pyro4.util

if sys.platform == "win32":
    import Console
else:
    import curses


QUEUE_SIZE = 1000
MB = 1024 * 1024

class StreamClient():
    def __init__(self, path):
        self.path = path
        self.cluster_size = 0
        self.files = {}
        self.file_progress = {}
        os.chdir(self.path)
        if os.path.isdir('Incomplete'):
            shutil.rmtree('Incomplete')
        if os.path.isdir('Complete'):
            shutil.rmtree('Complete')
        os.mkdir('Incomplete')
        os.mkdir('Complete')
        os.chdir('Incomplete')
        self.magic = FileMagic(self.path)
        self.queue = collections.deque()
        self.other = []
        self.handles = {}
        self.filenames = []
        self.residentfiles = {}
        if sys.platform == "win32":
            self.console = Console.getconsole()
            self.console.page()
            self.console.title("Running Stream Listener")
            self.console.text(0, 0, "Waiting for server...")
        else:
            curses.initscr()
            curses.noecho()
            curses.cbreak()
            self.win = curses.newwin(0,0)
            self.win.addstr(0, 0, "Waiting for server...")
            self.win.refresh()
        self.process = psutil.Process(os.getpid())
        self.totalmem = psutil.TOTAL_PHYMEM

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
        count = 0
        self.files = {}
        if sys.platform == "win32":
            self.console.text(0, 2, "Processing file entries...")
        else:
            self.win.clear()
            self.win.refresh()
            self.win.addstr(0, 0, "Processing file entries...")
            self.win.refresh()
        for entry in entries:
            # To try and prevent name collisions
            try:
                entry.name = str(entry.name)
            except:
                continue
            if entry.name in self.files or entry.name in self.residentfiles:
                entry.name = "[" + str(count) + "]" + "%sIncomplete/%s" % (self.path, entry.name)
                count += 1
            else:
                entry.name = "%sIncomplete/%s" % (self.path, entry.name)
            # NTFS is not consistent about where it stores a file's data size...
            """
            if entry.real_size == 0:
                if entry.data_size != 0:
                    self.files[entry.name] = [entry.data_size, entry.clusters]
                else:
                    # If no size data is present, resort to num of clusters * cluster size
                    # This is not the most reliable method, as it's common for the final cluster
                    # to be only partially filled.
                    if len(entry.clusters):
                        self.files[entry.name] = [len(entry.clusters) * self.cluster_size, entry.clusters]
                    else:
                        self.residentfiles[entry.name] = entry.res_data
            else:
                self.files[entry.name] = [entry.real_size, entry.clusters]
            """
            if entry.size != 0:
                self.files[entry.name] = [entry.size, entry.clusters]
            else:
                if len(entry.clusters):
                    self.files[entry.name] = [len(entry.clusters) * self.cluster_size, entry.clusters]
                else:
                    self.residentfiles[entry.name] = entry.res_data


    """
    Create a mapping of clusters to their respective files.
    """
    def setup_clustermap(self):
        for k, v in self.files.iteritems():
            for c in v[1]:
                self.clustermap[int(c)] = k

    """
    Create a dictionary containing the number of clusters each file is composed of.

    This will be used to determine if a file has been completely written to disk.
    """
    def setup_file_progress(self):
        self.file_progress = {}
        for file in self.files:
            self.file_progress[file] = len(self.files[file][1])

    """
    Create a list of all the clusters this client will be receiving.
    """
    def list_clusters(self):
        self.clusters = []
        for k, v in self.files.iteritems():
            try:
                self.clusters.extend(v[1])
            except:
                self.clusters.append(v[1])
        return self.clusters

    """
    Free up memory as this list is no longer necessary.
    """
    def clear_clusters(self):
        self.clusters = []
        gc.collect()

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


    def queue_showStatus(self):
        self.statusThread = threading.Thread(target=self.showStatus)
        self.statusThread.start()
        return

    """
    Writes file data to disk.

    The algorithm this function uses is an attempt to minimize random writes. This isn't all that straight-forward
    due to file-fragmentation and not having all of the data beforehand. I'm sure more efficient ones exist, but
    this does the job reasonably well.
    """
    def write_data(self):
        if sys.platform == "win32":
                self.console.text(0, 2, "Writing files to disk...")
        else:
            self.win.clear()
            self.win.refresh()
            self.win.addstr(0, 0, "Writing files to disk...")
            self.win.refresh()
        try:
            # While incomplete files remain...
            while len(self.file_progress):
                # Sleep while the queue is empty.
                while len(self.queue) == 0:
                    time.sleep(0.005)
                filedb = {}
                # 1000 is an arbitrary queue size to work on at one time.
                # This value can be adjusted for better performance.
                for idx in range(QUEUE_SIZE):
                    # This breaks us out of the loop if we weren't able to grab
                    # QUEUE_SIZE entries in one go.
                    if len(self.queue) == 0:
                        break
                    # Grab the front cluster/data set from the queue
                    cluster, data = self.queue.popleft()
                    # Create an in-memory db of mappings between files and their
                    # clusters/data that we've pulled off the queue.
                    try:
                        filedb[self.clustermap[cluster]].append((cluster, data))
                    except:
                        filedb[self.clustermap[cluster]] = [(cluster, data)]
                # For every file this iteration has data for...
                for file in filedb:
                    # Try to open the file if it exists, otherwise create it.
                    try:
                        fh = open(file, 'r+b')
                    except:
                        fh = open(file, 'wb')
                    # Create individual lists of the file's clusters and data we've obtained from the qeueue.
                    clusters, data = zip(*filedb[file])
                    idx = 0
                    num_clusters = len(clusters)
                    # For every cluster for this file we've received...
                    while idx < num_clusters:
                        buff = []
                        # Create an initial offset using the current index into the cluster array.
                        seek = clusters[idx]
                        # Add the data at the index into the "to be written buffer".
                        buff.append(data[idx])
                        try:
                            # If the next value in the cluster array is one more than the value at the index,
                            # include this in our buffer and increment the index. Continue doing so until
                            # we encounter a value that is not one more than the previous. This helps to
                            # maximize linear writes.
                            while clusters[idx + 1] == clusters[idx] + 1:
                                buff.append(data[idx + 1])
                                idx += 1
                        except:
                            pass
                        # Seek to the initial offset
                        fh.seek(self.files[file][1].index(seek) * self.cluster_size, os.SEEK_SET)
                        # Check to see if (initial offset + data length) > size of the file. This
                        # normally occurs because the file's size is not an exact multiple of the
                        # cluster size and thus the final cluster is zero padded. If this is so,
                        # trim off the padding.
                        if fh.tell() + len("".join(buff)) > int(self.files[file][0]):
                            left = int(self.files[file][0] - fh.tell())
                            out = "".join(buff)
                            fh.write(out[:left])
                            fh.flush()
                        # Otherwise just append the data.
                        else:
                            fh.write("".join(buff))
                            fh.flush()
                        # Subtract the number of clusters written from the file's remaining clusters list.
                        self.file_progress[file] -= len(buff)
                        del(buff)
                        idx += 1
                    fh.close()
                    # If the file's file_progress list is empty, then the entire file has been written to disk.
                    if not self.file_progress[file]:
                        del self.files[file]
                        del self.file_progress[file]
                        # Move file to appropriate folder based on its extension/magic number.
                        self.magic.process_file(file)
            # Write resident files to disk.
            for file in self.residentfiles:
                fh = open(file, 'wb')
                fh.write(self.residentfiles[file])
                fh.close()
                self.magic.process_file(file)
            # Finished. Do cleanup.
            ns.remove(name=sys.argv[1])
            daemon.shutdown()
        except KeyboardInterrupt:
            print 'User cancelled execution...'
            ns.remove(name=sys.argv[1])
            daemon.shutdown()


    def showStatus(self):
        num_files = len(self.files)
        starttime = int(time.time())
        if sys.platform == "win32":
            while True:
                time.sleep(1)
                self.console.text(0, 4, "%d of %d files remaining" % (len(self.file_progress), num_files))
                self.console.text(0, 6, "Client CPU usage: %d " % self.process.get_cpu_percent())
                self.console.text(0, 8, "Using %d MB of %d MB physical memory | %d MB physical memory free" %
                                  ((self.process.get_memory_info()[0] / MB), (self.totalmem / MB), (psutil.avail_phymem() / MB)))
                cur_write_rate = (self.process.get_io_counters()[3] / MB)
                duration = int(time.time()) - starttime
                self.console.text(0, 10, "Total bytes written to disk(MB): %d " % cur_write_rate)
                self.console.text(0, 12, "Average write rate: %d MB/s" % (cur_write_rate / duration))
                self.console.text(0, 14, "Duration: %0.2d:%0.2d:%0.2d" % ((duration/3600), (duration/60), (duration % 60)))
        else:
            while True:
                time.sleep(1)
                self.win.addstr(1, 0, "%d of %d files remaining" % (len(self.file_progress), num_files))
                self.win.addstr(2, 0, "Client CPU usage: %d " % self.process.get_cpu_percent())
                self.win.addstr(3, 0, "Using %d MB of %d MB physical memory | %d MB physical memory free" %
                                      ((self.process.get_memory_info()[0] / MB), (self.totalmem / MB), (psutil.avail_phymem() / MB)))
                cur_write_rate = (self.process.get_io_counters()[3] / MB)
                duration = int(time.time()) - starttime
                self.win.addstr(4, 0, "Total bytes written to disk: %d MB" % cur_write_rate)
                self.win.addstr(5, 0, "Average write rate: %d MB/s" % (cur_write_rate / duration))
                self.win.addstr(6, 0, "Duration: %0.2d:%0.2d:%0.2d" % ((duration/3600), (duration/60), (duration % 60)))
                self.win.refresh()


def main():
    daemon = Pyro4.core.Daemon(sys.argv[1])
    uri = daemon.register(StreamClient(path=sys.argv[3]))
    print "Host: %s\t\tPort: %i\t\tName: %s" % (socket.gethostname(), uri.port, sys.argv[2])
    ns = Pyro4.naming.locateNS()
    ns.register(sys.argv[2], uri)
    try:
        daemon.requestLoop()
    except KeyboardInterrupt:
        if sys.platform == "linux2":
            curses.nocbreak(); self.win.keypad(0); curses.echo()
            curses.endwin()
        print 'User aborted'
        ns.remove(name=sys.argv[2])
        daemon.shutdown()

if __name__ == "__main__":
    #try:
    #    import psyco
    #    psyco.full()
    #except:
    #    pass
    main()
