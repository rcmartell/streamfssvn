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

QUEUE_SIZE = 4096
MB = 1024 * 1024

class StreamClient():
    def __init__(self, path, name, ns, daemon):
        if not path.endswith(os.path.sep):
            self.path = path + os.path.sep
        else:
            self.path = path
        self.name = name
        self.ns = ns
        self.daemon = daemon
        self.cluster_size = 0
        self.files = {}
        self.file_progress = {}
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
        self.showCurrentStatus = True
        self.finished = False
        os.chdir(self.path)
        try:
            if os.path.exists("Incomplete"):
                shutil.rmtree("Incomplete")
        except:
            pass
        try:
            if os.path.exists("Complete"):
                shutil.rmtree("Complete")
        except:
            pass
        try:
            os.mkdir("Incomplete")
        except:
            pass
        try:
            os.mkdir("Complete")
        except:
            pass
        os.chdir("Incomplete")
        self.magic = FileMagic(self.path)
                

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
        self.clustermap = [0] * self.num_clusters

    """
    Setup necessary data structures to process entries received from Image Server.
    """
    def process_entries(self, entries):
        count = 0
        ncount = 0
        self.files = {}
        if sys.platform == "win32":
            self.console.text(0, 2, "Processing %d file entries..." % len(entries))
        else:
            self.win.clear()
            self.win.refresh()
            self.win.addstr(0, 0, "Processing %d file entries..." % len(entries))
            self.win.refresh()
        for entry in entries:
            # To try and prevent name collisions
            try:
                entry.name = unicode(entry.name, errors='ignore')
            except:
                print "Error in entryname: %s" % entry.name
                continue
            if entry.name in self.files or entry.name in self.residentfiles:
                entry.name = "[" + str(count) + "]" + "%sIncomplete/%s" % (self.path, entry.name)
                count += 1
            else:
                entry.name = "%sIncomplete/%s" % (self.path, entry.name)
            # NTFS is not consistent about where it stores a file's data size...
            if entry.size != 0:
                self.files[entry.name] = [entry.size, entry.clusters]
            else:
                if len(entry.clusters):
                    self.files[entry.name] = [len(entry.clusters) * self.cluster_size, entry.clusters]
                    ncount += 1
                else:
                    self.residentfiles[entry.name] = entry.res_data
        if sys.platform == "win32":
            self.console.text(0, 2, "Number of files missing size info: %d" % ncount)
            self.console.text(0, 4, "Number of resident files: %d" % len(self.residentfiles))
        else:
            self.win.clear()
            self.win.refresh()
            self.win.addstr(0, 0, "Number of files missing size info: %d" % ncount)
            self.win.addstr(1, 0, "Number of resident files: %d" % len(self.residentfiles))
            self.win.refresh()


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
        if sys.platform == "win32":
            self.console.text(0, 6, "FileProgress length: %d Files length: %d" % (len(self.file_progress), len(self.files)))
        else:
            self.win.clear()
            self.win.refresh()
            self.win.addstr(2, 0, "FileProgress length: %d Files length: %d" % (len(self.file_progress), len(self.files)))
            self.win.refresh()

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
        del(self.clusters)
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
        
    def check_status(self):
        return self.finished
        
    def set_finished(self):
        self.finished = True

    """
    Writes file data to disk.

    The algorithm this function uses is an attempt to minimize random writes. This isn't all that straight-forward
    due to file-fragmentation and not having all of the data beforehand. I'm sure more efficient ones exist, but
    this does the job reasonably well.
    """
    def write_data(self):
        if sys.platform == "win32":
                self.console.text(0, 8, "Writing files to disk...")
        else:
            self.win.clear()
            self.win.refresh()
            self.win.addstr(3, 0, "Writing files to disk...")
            self.win.refresh()
        try:
            # While incomplete files remain...
            while len(self.file_progress):
                # Sleep while the queue is empty.
                if len(self.queue) == 0:
                    if self.finished:
                        if sys.platform == "win32":
                            self.console.text(0, 30, "Error. Unable to write all files to disk. %d files left unwritten." % len(self.file_progress))
                        else:
                            self.win.clear()
                            self.win.refresh()
                            self.win.addstr(14, 0, "Error. Unable to write all files to disk. %d files left unwritten." % len(self.file_progress))
                            self.win.refresh()
                        fh = open("%s-ErrorLog" % self.name, "wb")
                        for file in self.file_progress:
                            fh.write(str(file) + ": %d" % self.file_progress[file])
                            fh.write("\n")
                        fh.flush()
                        fh.close()
                        break
                    else:
                        time.sleep(0.005)
                        continue
                filedb = {}
                # QUEUE_SIZE is an arbitrary queue size to work on at one time.
                # This value can be adjusted for better performance.
                for idx in range(QUEUE_SIZE):
                    # This breaks us out of the loop if we weren't able to grab
                    # QUEUE_SIZE entries in one go.
                    if len(self.queue) == 0:
                        if self.finished:
                            break
                        else:
                            time.sleep(0.005)
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
                for file in filedb:
                    # Try to open the file if it exists, otherwise create it.
                    try:
                        fh = open(file, 'r+b')
                    except:
                        try:
                            fh = open(file, 'wb')
                        except:
                            if file in self.file_progress:
                                del(self.file_progress[file])
                            continue
                    # Create individual lists of the file's clusters and data we've obtained from the qeueue.
                    clusters, data = zip(*filedb[file])
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
                        idx += 1
                        buff = []
                    fh.close()
                    # If the file's file_progress list is empty, then the entire file has been written to disk.
                    if not self.file_progress[file]:
                        del self.files[file]
                        del self.file_progress[file]
                        # Move file to appropriate folder based on its extension/magic number.
                        self.magic.process_file(file)
            # Write resident files to disk.
            if sys.platform == "win32":
                self.console.text(0, 28, "Writing %d resident files to disk..." % len(self.residentfiles))
            else:
                self.win.clear()
                self.win.refresh()
                self.win.addstr(13, 0, "Writing %d resident files to disk..." % len(self.residentfiles))
                self.win.refresh()
            for file in self.residentfiles:
                try:
                    fh = open(file, 'wb')
                    fh.write(self.residentfiles[file])
                    fh.close()
                    self.magic.process_file(file)
                except:
                    pass
            # Finished. Do cleanup.
            self.finished = True
            self.showCurrentStatus = False
            self.ns.remove(name=self.name)
            self.daemon.shutdown()
        except KeyboardInterrupt:
            print 'User cancelled execution...'
            if sys.platform == "win32":
                self.console.text(0, 28, "Writing %d resident files to disk..." % len(self.residentfiles))
            else:
                self.win.clear()
                self.win.refresh()
                self.win.addstr(13, 0, "Writing %d resident files to disk..." % len(self.residentfiles))
                self.win.refresh()
                for file in self.residentfiles:
                    try:
                        fh = open(file, 'wb')
                        fh.write(self.residentfiles[file])
                        fh.close()
                        self.magic.process_file(file)
                    except:
                        pass
            self.showCurrentStatus = False
            curses.nocbreak(); self.win.keypad(0); curses.echo()
            curses.endwin()
            self.ns.remove(name=self.name)
            self.daemon.shutdown()


    def showStatus(self):
        num_files = len(self.files)
        starttime = int(time.time())
        if sys.platform == "win32":
            while self.showCurrentStatus:
                try:
                    time.sleep(1)
                    self.console.text(0, 12, "%d of %d files remaining     " % (len(self.file_progress), num_files))
                    self.console.text(0, 14, "Clusters in queue: %d           " % len(self.queue))
                    self.console.text(0, 16, "Client CPU usage: %d  " % self.process.get_cpu_percent())
                    self.console.text(0, 18, "Using %d MB of %d MB physical memory | %d MB physical memory free      " %
                                      ((self.process.get_memory_info()[0] / MB), (self.totalmem / MB), (psutil.avail_phymem() / MB)))
                    cur_write_rate = (self.process.get_io_counters()[3] / MB)
                    duration = int(time.time()) - starttime
                    self.console.text(0, 20, "Total bytes written to disk(MB): %d   " % cur_write_rate)
                    self.console.text(0, 22, "Average write rate: %d MB/s       " % (cur_write_rate / duration))
                    self.console.text(0, 24, "Duration: %0.2d:%0.2d:%0.2d" % ((duration/3600), ((duration/60) % 60), (duration % 60)))
                except:
                    pass
        else:
            while self.showCurrentStatus:
                try:
                    time.sleep(1)
                    self.win.addstr(5, 0, "%d of %d files remaining              " % (len(self.file_progress), num_files))
                    self.win.addstr(6, 0, "Clusters in queue: %d           " % len(self.queue))
                    self.win.addstr(7, 0, "Client CPU usage: %d  " % self.process.get_cpu_percent())
                    self.win.addstr(8, 0, "Using %d MB of %d MB physical memory | %d MB physical memory free        " %
                                          ((self.process.get_memory_info()[0] / MB), (self.totalmem / MB), (psutil.avail_phymem() / MB)))
                    cur_write_rate = (self.process.get_io_counters()[3] / MB)
                    duration = int(time.time()) - starttime
                    self.win.addstr(9, 0, "Total bytes written to disk: %d MB          " % cur_write_rate)
                    self.win.addstr(10, 0, "Average write rate: %d MB/s          " % (cur_write_rate / duration))
                    self.win.addstr(11, 0, "Duration: %0.2d:%0.2d:%0.2d" % ((duration/3600), ((duration/60) % 60), (duration % 60)))
                    self.win.refresh()
                except:
                    pass


def main():
    try:
        daemon = Pyro4.core.Daemon(sys.argv[1])
        name = sys.argv[2]
        filepath = sys.argv[3]
    except:
        daemon = Pyro4.core.Daemon('127.0.0.1')
        name = sys.argv[1]
        filepath = sys.argv[2]
    ns = Pyro4.naming.locateNS()
    client = StreamClient(path=filepath, name=name, ns=ns, daemon=daemon)
    uri = daemon.register(client)
    print "Host: %s\t\tPort: %i\t\tName: %s" % (socket.gethostname(), uri.port, name)
    ns.register(name, uri)
    try:
        daemon.requestLoop()
    except KeyboardInterrupt:
        if sys.platform == "linux2":
            curses.nocbreak(); client.win.keypad(0); curses.echo()
            curses.endwin()
        print 'User aborted'
        ns.remove(name=name)
        daemon.shutdown()

if __name__ == "__main__":
    main()
