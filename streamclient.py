#!/usr/bin/python
import sys, os, time, shutil, argparse, curses
import threading, socket, gc
from collections import deque
from filehandler import FileHandler
import warnings, psutil
warnings.filterwarnings("ignore")
import Pyro4.core, Pyro4.naming
from multiprocessing import Process, Queue

QUEUE_SIZE = 8192
MB = 1024 * 1024

class StreamClient():
    def __init__(self, path, name, ns, daemon):
        self.path = path
        self.name = name
        self.ns = ns
        self.daemon = daemon
        self.files = {}
        self.file_progress = {}
        self.filenames = []
        self.residentfiles = {}
        self.show_current_status = True
        self.throttle = False
        self.finished = False
        self.queue = deque()
        self.setup_status_ui()
        self.setup_folders()
        self.setup_file_handler()

    def setup_status_ui(self):
        curses.initscr(); curses.noecho(); curses.cbreak()
        self.stdscr = curses.newwin(0,0)
        self.stdscr.clear()
        self.stdscr.addstr(0, 0, "Waiting for server...")
        self.stdscr.refresh()

    def setup_folders(self):
        os.chdir(self.path)
        if os.path.isdir('Incomplete'):
            shutil.rmtree('Incomplete')
        os.mkdir('Incomplete')
        if os.path.isdir('Complete'):
            shutil.rmtree('Complete')
        os.mkdir('Complete')
        os.chdir('Incomplete')

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

    def setup_file_handler(self):
        self.file_handler = FileHandler(self.path)
        self.file_queue = Queue()
        self.proc = Process(target=self.file_handler.handler_queue, args=(self.file_queue,))
        self.proc.daemon = True
        self.proc.start()

    def process_entries(self, entries):
        """
        Setup necessary data structures to process entries received from Image Server.
        """
        self.stdscr.clear()
        self.stdscr.addstr(0, 0, "Processing file entries...")
        self.stdscr.refresh()
        for entry in entries:
            try:
                entry.name = "{0}{1}Incomplete{1}{2}".format(self.path, os.path.sep, str(entry.name).replace("/", "]["))
            except:
                continue
            if entry.res_data != None:
                # File is resident
                self.residentfiles[entry.name] = entry.res_data
            else:
                # Nonresident
                self.files[entry.name] = [entry.size, reduce(lambda x, y: x+y, [range(idx[0], idx[0] + idx[1]) for idx in entry.clusters])]
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
        for _file in self.files:
            self.file_progress[_file] = len(self.files[_file][1])
        return

    def list_clusters(self):
        """
        Create a list of all the clusters this client will be receiving.
        """
        return [x for v in self.files.itervalues() for x in v[1]]

    def add_queue(self, items):
        """
        Method used by Image Server to transfer cluster/data to client.
        """
        self.queue.extend(items)
        
    def get_queue_size(self):
        return len(self.queue)

    def throttle_needed(self):
        return self.throttle

    def queue_writes(self):
        """
        Helper method to spawn write_data in a seperate thread.
        """
        self.thread = threading.Thread(target=self.write_data)
        self.thread.start()
        return

    def queue_show_status(self):
        self.statusThread = threading.Thread(target=self.show_status)
        self.statusThread.setDaemon(True)
        self.statusThread.start()
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
                for _file in filedb:
                    # Try to open the file if it exists, otherwise create it.
                    try:
                        fh = open(_file, 'r+b')
                    except:
                        fh = open(_file, 'wb')
                    # Create individual lists of the file's clusters and data we've obtained from the qeueue.
                    clusters, data = zip(*filedb[_file])
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
                        fh.seek(self.files[_file][1].index(seek) * self.cluster_size, os.SEEK_SET)
                        # Check to see if (initial offset + data length) > size of the file. This
                        # normally occurs because the file's size is not an exact multiple of the
                        # cluster size and thus the final cluster is zero padded. If this is so,
                        # trim off the padding.
                        if fh.tell() + len("".join(buff)) > int(self.files[_file][0]):
                            left = int(self.files[_file][0] - fh.tell())
                            out = "".join(buff)
                            fh.write(out[:left])
                            fh.flush()
                        # Otherwise just append the data.
                        else:
                            fh.write("".join(buff))
                            fh.flush()
                        # Subtract the number of clusters written from the file's remaining clusters list.
                        self.file_progress[_file] -= len(buff)
                        idx += 1
                        buff = []
                    fh.close()
                    # If the file's file_progress list is empty, then the entire file has been written to disk.
                    if not self.file_progress[_file]:
                        del self.files[_file]
                        del self.file_progress[_file]
                        # Move file to appropriate folder based on its extension/sorter number.
                        self.file_queue.put_nowait(_file)
            # Write resident files to disk.
            for res_file in self.residentfiles:
                fh = open(res_file, 'wb')
                fh.write(self.residentfiles[res_file])
                fh.close()
                self.file_queue.put_nowait(res_file)
            self.file_handler.running = False
            self.proc.join()
            self.show_status = False
            self.ns.remove(name=name)
            return
        except KeyboardInterrupt:
            print 'User cancelled execution...'
            self.show_status = False
            self.file_handler.running = False
            self.ns.remove(name=name)
            return


    def show_status(self):
        try:
            num_files = len(self.files)
            start_time = int(time.time())
            process = psutil.Process(os.getpid())
            total_mem = psutil.TOTAL_PHYMEM
            avail_phymem = psutil.avail_phymem
            get_cpu_percent = process.get_cpu_percent
            get_memory_info = process.get_memory_info
            prev_bytes_written, cur_idle, total_idle = 0, 0, 0
            phymem_buffers = psutil.phymem_buffers
            cached_phymem = psutil.cached_phymem
            while self.show_status:
                time.sleep(3)
                if len(self.queue) >= 524288:
                    self.throttle = True
                    time.sleep(3)
                else:
                    self.throttle = False
                cur_write_rate = (process.get_io_counters()[3] / MB)
                duration = int(time.time()) - start_time
                self.stdscr.addstr(0, 0, "{0} of {1} files remaining {2:<30s}".format(len(self.file_progress), num_files, ''))
                self.stdscr.addstr(1, 0, "Clusters in queue: {0:<30d}".format(len(self.queue)))
                self.stdscr.addstr(2, 0, "Client CPU usage: {0:<30d}".format(int(get_cpu_percent())))
                #self.stdscr.addstr(3, 0, "Using {0} MB of {1} MB physical memory | {2} MB physical memory free {3:<20s}".format
                #                      ((get_memory_info()[0] / MB), (total_mem / MB), ((avail_phymem() +
                #                      cached_phymem() + phymem_buffers()) / MB), ''))
                self.stdscr.addstr(4, 0, "Total bytes written to disk(MB): {0:<30d}".format(cur_write_rate))
                try:
                    self.stdscr.addstr(5, 0, "Average write rate: {0} MB/s {1:<30s}".format((cur_write_rate / (duration)), ''))
                except:
                    self.stdscr.addstr(5, 0, "Average write rate: {0} MB/s {1:<30}".format((cur_write_rate / duration), ''))
                #self.stdscr.addstr(6, 0, "Current idle time: {0:02d}:{1:02d}:{2:02d}".format((cur_idle/3600), ((cur_idle/60) % 60), (cur_idle % 60)))
                #self.stdscr.addstr(7, 0, "Total idle time: {0:02d}:{1:02d}:{2:02d}".format((total_idle/3600), ((total_idle/60) % 60), (total_idle % 60)))
                self.stdscr.addstr(8, 0, "Duration: {0:02d}:{1:02d}:{2:02d}".format((duration/3600), ((duration/60) % 60), (duration % 60)))
                if self.throttle:
                    self.stdscr.addstr(9, 0, "Throttling...")
                else:
                    self.stdscr.addstr(9, 0, "{0:<30s}".format(''))
                    self.stdscr.move(9, 0)
                self.stdscr.refresh()
                #prev_bytes_written = cur_write_rate
            curses.nocbreak(); stdscr.keypad(0); curses.echo()
            curses.endwin()
            self.ns.remove(name=name)
        except KeyboardInterrupt:
            if sys.platform == "linux2":
                curses.nocbreak(); stdscr.keypad(0); curses.echo()
                curses.endwin()
            print 'User aborted'
            self.ns.remove(name=name)
            return

def main():
    argparser = argparse.ArgumentParser()
    argparser.add_argument('-p', '--path', help = "Root directory for client. Files will be written and processed here. Defaults to the current working directory if no value is specified.", required = False)
    argparser.add_argument('-i', '--id', help = "Unique name/identifier used to register the client with the Pyro nameserver.", required = True)
    args = argparser.parse_args()
    opts = vars(args)
    name = opts['id']
    path = opts['path']
    if path == None:
        path = os.path.abspath(os.path.curdir)
    elif not os.path.lexists(path):
        print "Invalid path specified."
        sys.exit(-1)
    if path.endswith(os.path.sep):
        path = path[:-1]
    # Start Pyro daemon
    daemon = Pyro4.core.Daemon(socket.gethostname())
    ns = Pyro4.naming.locateNS()
    client = StreamClient(name=name, path=path, ns=ns, daemon=daemon)
    uri = daemon.register(client)
    ns.register(name, uri)
    try:
        daemon.requestLoop()
    except KeyboardInterrupt:
        print 'User aborted'
        curses.nocbreak(); stdscr.keypad(0); curses.echo()
        curses.endwin()
        ns.remove(name=name)
        daemon.shutdown()
        sys.exit(-1)

if __name__ == "__main__":
	main()
