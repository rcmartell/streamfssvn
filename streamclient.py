#!/usr/bin/python
import sys, os, time, shutil
import threading, socket, collections, gc
from filehandler import FileHandler
import warnings, psutil
warnings.filterwarnings("ignore")
import Pyro4.core, Pyro4.naming
from multiprocessing import Process, Queue

if sys.platform == "win32":
    try:
        import Console #@UnresolvedImport
    except:
        pass
else:
    try:
        import curses
    except:
        pass

QUEUE_SIZE = 8192
MB = 1024 * 1024

class StreamClient():
    def __init__(self, path, name, ns, daemon):
        if path.endswith(os.path.sep):
            self.path = path[:-1]
        else:
            self.path = path
        self.name = name
        self.ns = ns
        self.daemon = daemon
        self.cluster_size = 0
        self.files = {}
        self.file_progress = {}
        os.chdir(self.path)
        if os.path.isdir('Incomplete'):
            shutil.rmtree('Incomplete')
        os.mkdir('Incomplete')
        if os.path.isdir('Complete'):
            shutil.rmtree('Complete')
        os.mkdir('Complete')
        os.chdir('Incomplete')
        self.fileHandler = FileHandler(self.path)
        self.processQueue = Queue()
        self.proc = Process(target=self.fileHandler.processFiles, args=(self.processQueue,)).start()
        self.queue = collections.deque()
        self.filenames = []
        self.residentfiles = {}
#        if sys.platform == "win32":
#            self.console = Console.getconsole()
#            self.console.page()
#            self.console.title("Running Stream Listener")
#            self.console.text(0, 0, "Waiting for server...")
#        else:
#            curses.initscr(); curses.noecho(); curses.cbreak()
#            self.win = curses.newwin(0,0)
#            self.win.addstr(0, 0, "Waiting for server...")
#            self.win.refresh()
        self.process = psutil.Process(os.getpid())
        self.totalmem = psutil.TOTAL_PHYMEM
        self.showCurrentStatus = True
        self.throttle = False
        self.finished = False

    def set_cluster_size(self, size):
        """
        Set by Image Server
        """
        self.cluster_size = int(size)
        return

    def set_num_clusters(self, num):
        """
        Set by Image Server
        """
        self.num_clusters = int(num)
        self.clustermap = [-1] * self.num_clusters
        return

    def process_entries(self, entries):
        """
        Setup necessary data structures to process entries received from Image Server.
        """
#        if sys.platform == "win32":
#            self.console.text(0, 2, "Processing file entries...")
#        else:
#            self.win.clear()
#            self.win.addstr(0, 0, "Processing file entries...")
#            self.win.refresh()
        count = 0
        for entry in entries:
<<<<<<< .mine
            entry.name = "%s/Incomplete/%s" % (self.path, str(entry.name))
            print entry.name
            if entry.name in self.files or entry.name in self.residentfiles:
                # To try and prevent name collisions
               entry.name = "%s/Incomplete/[" % self.path + str(count) + "]%s" % entry.name.split("Incomplete/")[1]
               count += 1
            if entry.res_data != None and len(entry.res_data) > 0:
=======
            try:
                entry.name = "{0}{1}Incomplete{1}{2}" % (self.path, os.path.sep, str(entry.name).replace("/", "&"))
            except:
                continue
            if entry.res_data != None:
>>>>>>> .r290
                # File is resident
                self.residentfiles[entry.name] = entry.res_data
            else:
                # Nonresident
<<<<<<< .mine
                self.files[entry.name] = [entry.size, reduce(lambda x, y: x+y, [range(idx[0], idx[0] + idx[1]) for idx in entry.clusters])]
                print self.files[entry.name]
=======
                self.files[entry.name] = [entry.size, reduce(lambda x, y: x+y, [range(idx[0], idx[0] + idx[1]) for idx in entry.clusters])]
>>>>>>> .r290
        del(entries)
        gc.collect()
        return


    def setup_clustermap(self):
        """
        Create a mapping of clusters to their respective files.
        """
        for k, v in self.files.iteritems():
            for c in v[1]:
                self.clustermap[int(c)] = k
        return

    def setup_file_progress(self):
        """
        Create a dictionary containing the number of clusters each file is composed of.
        This will be used to determine if a file has been completely written to disk.
        """
        for f in self.files:
            self.file_progress[f] = len(self.files[f][1])
        return

    def list_clusters(self):
        """
        Create a list of all the clusters this client will be receiving.
        """
        self.clusters = []
        for v in self.files.itervalues():
            try:
                self.clusters.extend(v[1])
            except:
                self.clusters.append(v[1])
        return self.clusters

    def clear_clusters(self):
        """
        Free up memory as this list is no longer necessary.
        """
        self.clusters = []
        del(self.clusters)
        gc.collect()
        return

    def add_queue(self, cluster, data):
        """
        Method used by Image Server to transfer cluster/data to client.
        """
        self.queue.extend(zip(cluster, data))
        return self.throttle

    def throttle_needed(self):
        return self.throttle

    def queue_writes(self):
        """
        Helper method to spawn write_data in a seperate thread.
        """
        self.thread = threading.Thread(target=self.write_data)
        self.thread.start()
        return

    def queue_showStatus(self):
<<<<<<< .mine
<<<<<<< .mine
        #self.statusThread = threading.Thread(target=self.showStatus)
        #self.statusThread.start()
=======
        self.clientStatus = StreamClientStatus()        
        #self.statusThread = threading.Thread(target=self.showStatus)
        #self.statusThread.start()
=======
        self.statusThread = threading.Thread(target=self.showStatus)
        self.statusThread.start()
>>>>>>> .r294
>>>>>>> .r290
        return

    def set_finished(self):
        self.finished = True
        return

    def write_data(self):
        """
        Writes file data to disk.

        The algorithm this function uses is an attempt to minimize random writes. This isn't all that straight-forward
        due to file-fragmentation and not having all of the data beforehand. I'm sure more efficient ones exist, but
        this does the job reasonably well.
        """
        try:
            # While incomplete files remain...
            while len(self.file_progress):
                # Sleep while the queue is empty.
                if not len(self.queue):
                    time.sleep(1)
                filedb = {}
                # QUEUE_SIZE is an arbitrary queue size to work on at one time.
                # This value can be adjusted for better performance.
                for idx in xrange(QUEUE_SIZE):
                    # This breaks us out of the loop if we weren't able to grab
                    # QUEUE_SIZE entries in one go. We're not using break so that
                    # we can hopefully fill up filedb which helps in consolidating
                    # writes to disk.
                    if len(self.queue) == 0:
                        continue
                    # Grab the front cluster/data set from the queue
                    cluster, data = self.queue.popleft()
                    # Create an in-memory db of mappings between files and their
                    # clusters/data that we've pulled off the queue.
                    try:
                        filedb[self.clustermap[cluster]].append((cluster, data))
                    except:
                        filedb[self.clustermap[cluster]] = [(cluster, data)]
                # For every file this iteration has data for...
                for f in filedb:
                    # Try to open the file if it exists, otherwise create it.
                    try:
                        fh = open(f, 'r+b')
                    except:
                        fh = open(f, 'wb')
                    # Create individual lists of the file's clusters and data we've obtained from the qeueue.
                    clusters, data = zip(*filedb[f])
                    idx = 0
                    num_clusters = len(clusters)
                    buff = []
                    # For every cluster for this file we've received...
                    while idx < num_clusters:
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
                        fh.seek(self.files[f][1].index(seek) * self.cluster_size, os.SEEK_SET)
                        # Check to see if (initial offset + data length) > size of the file. This
                        # normally occurs because the file's size is not an exact multiple of the
                        # cluster size and thus the final cluster is zero padded. If this is so,
                        # trim off the padding.
                        if fh.tell() + len("".join(buff)) > int(self.files[f][0]):
                            left = int(self.files[f][0] - fh.tell())
                            out = "".join(buff)
                            fh.write(out[:left])
                            fh.flush()
                        # Otherwise just append the data.
                        else:
                            fh.write("".join(buff))
                            fh.flush()
                        # Subtract the number of clusters written from the file's remaining clusters list.
                        self.file_progress[f] -= len(buff)
                        idx += 1
                        buff = []
                    fh.close()
                    # If the file's file_progress list is empty, then the entire file has been written to disk.
                    if not self.file_progress[f]:
                        del self.files[f]
                        del self.file_progress[f]
                        # Move file to appropriate folder based on its extension/sorter number.
                        self.processQueue.put_nowait(f)
            # Write resident files to disk.
            for f in self.residentfiles:
                fh = open(f, 'wb')
                fh.write(self.residentfiles[f])
                fh.close()
                self.processQueue.put_nowait(f)
            self.showCurrentStatus = False
            self.fileHandler.running = False
            self.ns.remove(name=sys.argv[1])
            self.daemon.shutdown()
            return
        except KeyboardInterrupt:
            print 'User cancelled execution...'
            self.showCurrentStatus = False
            self.fileHandler.running = False
            self.ns.remove(name=sys.argv[1])
            self.daemon.shutdown()
            return

<<<<<<< .mine
#    def showStatus(self):
#        num_files = len(self.files)
#        starttime = int(time.time())
#        prev_bytes_written, cur_idle, total_idle = 0, 0, 0
#        if sys.platform == "win32":
#            while self.showCurrentStatus:
#                time.sleep(1)
#                if (psutil.avail_phymem() / MB) < 512:
#                    self.throttle = True
#                else:
#                    self.throttle = False
#                cur_write_rate = (self.process.get_io_counters()[3] / MB)
#                duration = int(time.time()) - starttime
#                self.console.text(0, 4, "%d of %d files remaining     " % (len(self.file_progress), num_files))
#                self.console.text(0, 6, "Clusters in queue: %d           " % len(self.queue))
#                self.console.text(0, 8, "Client CPU usage: %d  " % self.process.get_cpu_percent())
#                self.console.text(0, 10, "Using %d MB of %d MB physical memory | %d MB physical memory free      " %
#                                  ((self.process.get_memory_info()[0] / MB), (self.totalmem / MB), (psutil.avail_phymem() / MB)))
#                self.console.text(0, 12, "Total bytes written to disk(MB): %d   " % cur_write_rate)
#                self.console.text(0, 14, "Average write rate: %d MB/s       " % (cur_write_rate / duration))
#                self.console.text(0, 16, "Duration: %0.2d:%0.2d:%0.2d" % ((duration/3600), ((duration/60) % 60), (duration % 60)))
#        else:
#            while self.showCurrentStatus:
#                time.sleep(1)
#                if ((psutil.avail_phymem() + psutil.cached_phymem() + psutil.phymem_buffers()) / MB) < 512:
#                    self.throttle = True
#                else:
#                    self.throttle = False
#                cur_write_rate = (self.process.get_io_counters()[3] / MB)
#                duration = int(time.time()) - starttime
#                if cur_write_rate == prev_bytes_written:
#                    cur_idle += 1
#                    total_idle += 1
#                else:
#                    cur_idle = 0
#                prev_bytes_written = cur_write_rate
#                self.win.addstr(0, 0, "%d of %d files remaining              " % (len(self.file_progress), num_files))
#                self.win.addstr(1, 0, "Clusters in queue: %d           " % len(self.queue))
#                self.win.addstr(2, 0, "Client CPU usage: %d  " % self.process.get_cpu_percent())
#                self.win.addstr(3, 0, "Using %d MB of %d MB physical memory | %d MB physical memory free        " %
#                                      ((self.process.get_memory_info()[0] / MB), (self.totalmem / MB), ((psutil.avail_phymem() +
#                                      psutil.cached_phymem() + psutil.phymem_buffers()) / MB)))
#                self.win.addstr(4, 0, "Total bytes written to disk: %d MB          " % cur_write_rate)
#                try:
#                    self.win.addstr(5, 0, "Average write rate: %d MB/s          " % (cur_write_rate / (duration - total_idle)))
#                except:
#                    self.win.addstr(5, 0, "Average write rate: %d MB/s          " % (cur_write_rate / duration))
#                self.win.addstr(6, 0, "Current idle time: %0.2d:%0.2d:%0.2d" % ((cur_idle/3600), ((cur_idle/60) % 60), (cur_idle % 60)))
#                self.win.addstr(7, 0, "Total idle time: %0.2d:%0.2d:%0.2d" % ((total_idle/3600), ((total_idle/60) % 60), (total_idle % 60)))
#                self.win.addstr(8, 0, "Duration: %0.2d:%0.2d:%0.2d" % ((duration/3600), ((duration/60) % 60), (duration % 60)))
#                if self.throttle:
#                    self.win.addstr(9, 0, "Throttling...")
#                else:
#                    self.win.addstr(9, 0, "                       ")
#                    self.win.move(9, 0)
#                self.win.refresh()
=======
    def showStatus(self):
        num_files = len(self.files)
        starttime = int(time.time())
        prev_bytes_written, cur_idle, total_idle = 0, 0, 0
        if sys.platform == "win32":
            while self.showCurrentStatus:
                time.sleep(2)
                if (psutil.avail_phymem() / MB) < 512:
                    self.throttle = True
                else:
                    self.throttle = False
                cur_write_rate = (self.process.get_io_counters()[3] / MB)
                duration = int(time.time()) - starttime
                self.console.text(0, 4, "{0} of {1} files remaining{2:<20d}".format(len(self.file_progress), num_files, ''))
                self.console.text(0, 6, "Clusters in queue: {0:<20d}".format(len(self.queue)))
                self.console.text(0, 8, "Client CPU usage: {0:<20d}".format(self.process.get_cpu_percent()))
                self.console.text(0, 10, "Using {0} MB of {1} MB physical memory | {2} MB physical memory free{3:<10d}".format(
                                  (self.process.get_memory_info()[0] / MB), (self.totalmem / MB), (psutil.avail_phymem() / MB), ''))
                self.console.text(0, 12, "Total bytes written to disk(MB): {0:<20d}".format(cur_write_rate))
                self.console.text(0, 14, "Average write rate: {0} MB/s{1:<10d}".format((cur_write_rate / duration), ''))
                self.console.text(0, 16, "Duration: {0:02d}:{1:02d}:{2:02d}".format((duration/3600), ((duration/60) % 60), (duration % 60)))
        else:
            while self.showCurrentStatus:
                time.sleep(2)
                if ((psutil.avail_phymem() + psutil.cached_phymem() + psutil.phymem_buffers()) / MB) < 512:
                    self.throttle = True
                else:
                    self.throttle = False
                cur_write_rate = (self.process.get_io_counters()[3] / MB)
                duration = int(time.time()) - starttime
                if cur_write_rate == prev_bytes_written:
                    cur_idle += 1
                    total_idle += 1
                else:
                    cur_idle = 0
                prev_bytes_written = cur_write_rate
                self.win.addstr(0, 0, "{0} of {1} files remaining{2:<20d}".format(len(self.file_progress), num_files, ''))
                self.win.addstr(1, 0, "Clusters in queue: {0:<20d}".format(len(self.queue)))
                self.win.addstr(2, 0, "Client CPU usage: {0:<20d}".format(self.process.get_cpu_percent()))
                self.win.addstr(3, 0, "Using {0} MB of {1} MB physical memory | {2} MB physical memory free{3:<10d}".format(
                                      (self.process.get_memory_info()[0] / MB), (self.totalmem / MB), ((psutil.avail_phymem() +
                                      psutil.cached_phymem() + psutil.phymem_buffers()) / MB)))
                self.win.addstr(4, 0, "Total bytes written to disk(MB): {0:<20d}".format(cur_write_rate))
                try:
                    self.win.addstr(5, 0, "Average write rate: {0} MB/s{1:<10d}".format(cur_write_rate / (duration - total_idle)))
                except:
                    self.win.addstr(5, 0, "Average write rate: {0} MB/s{1:<10d}".format(cur_write_rate / duration))
                self.win.addstr(6, 0, "Current idle time: {0:02d}:{1:02d}:{2:02d}".format((cur_idle/3600), ((cur_idle/60) % 60), (cur_idle % 60)))
                self.win.addstr(7, 0, "Total idle time:{0:02d}:{1:02d}:{2:02d}".format((total_idle/3600), ((total_idle/60) % 60), (total_idle % 60)))
                self.win.addstr(8, 0, "Duration: {0:02d}:{1:02d}:{2:02d}".format((duration/3600), ((duration/60) % 60), (duration % 60)))
                if self.throttle:
                    self.win.addstr(9, 0, "Throttling...")
                else:
                    self.win.addstr(9, 0, "{0:<30s}".format(''))
                    self.win.move(9, 0)
                self.win.refresh()
>>>>>>> .r290

def main():
    # Start Pyro daemon
    daemon = Pyro4.core.Daemon(socket.gethostname())
    ns = Pyro4.naming.locateNS()
    uri = daemon.register(StreamClient(name=sys.argv[1], path=sys.argv[2], ns=ns, daemon=daemon))
    ns.register(sys.argv[1], uri)
    try:
        daemon.requestLoop()
    except KeyboardInterrupt:
        if sys.platform == "linux2":
            curses.nocbreak(); curses.echo(); curses.endwin(); os.system("reset")
        print 'User aborted'
        ns.remove(name=sys.argv[1])
        daemon.shutdown()
        sys.exit(-1)

if __name__ == "__main__":
    main()
