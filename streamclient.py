#!/usr/bin/python
import sys, os, time, shutil, argparse, curses
import threading, socket, gc
from collections import deque
from filehandler import FileHandler
import warnings, psutil
warnings.filterwarnings("ignore")
import Pyro4.core, Pyro4.naming
from multiprocessing import Process, Queue
from time import time

QUEUE_SIZE = 65536 
MB = 1024 * 1024

class StreamClient():
    def __init__(self, path, name, config_path, ns, daemon):
        self.path = path
        self.name = name
        self.config_path = config_path
        self.ns = ns
        self.daemon = daemon
        self.files = {}
        self.file_progress = {}
        self.filenames = []
        self.residentfiles = {}
        self.show_status = True
        self.throttle = False
        self.finished = False
        self.bytes_written = 0
        self.queue = deque()
        self.setup_folders()
        self.setup_status_ui()

    def clear_screen(self):
        if sys.platform == 'linux2':
            os.system("clear")
        else:
            os.system("cls")

    def setup_status_ui(self):
        self.clear_screen()
        print("\033[0;0HWaiting for server...")
        return
        
    def setup_folders(self):
        self.clear_screen()
        os.chdir(self.path)
        if os.path.isdir('{0}{1}Incomplete'.format(self.path, os.path.sep)):
            answ = raw_input('{0}{1}Incomplete'.format(self.path, os.path.sep) +  " already exists. Delete Y/[N]")
            if answ.upper() == 'Y':
                shutil.rmtree('Incomplete')
                os.mkdir('{0}{1}Incomplete'.format(self.path, os.path.sep))
        else:
            os.mkdir('{0}{1}Incomplete'.format(self.path, os.path.sep))
        if os.path.isdir('{0}{1}Complete'.format(self.path, os.path.sep)):
            answ = raw_input('{0}{1}Complete'.format(self.path, os.path.sep) +  " already exists. Delete Y/[N]")
            if answ.upper() == 'Y':
                shutil.rmtree('Complete')
                os.mkdir('Complete')
        else:
            os.mkdir('Complete')

    def set_cluster_size(self, size):
        """
        Set by Image Server1
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
        self.handler = FileHandler()
        self.file_queue = Queue()
        self.proc = Process(target=self.handler.handler_queue, args=(self.file_queue,))
        self.proc.start()

    def process_entries(self, entries):
        """
        Setup necessary data structures to process entries received from Image Server.
        """
        self.clear_screen()
        print("\033[0;0HProcessing file entries...")
        for entry in entries:
            try:
                entry.name = "{0}{1}Incomplete{1}{2}".format(self.path, os.path.sep, str(entry.name).replace("/", "\\"))
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
        self.statusThread = threading.Thread(target=self.show_status_info)
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
            popleft_queue = self.queue.popleft
            # While incomplete files remain...
            while len(self.file_progress):
                # Sleep while the queue is empty.
                while not len(self.queue):
                    sleep(0.0005)
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
                    cluster, data = popleft_queue()
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
                    write = fh.write
                    seek = fh.seek
                    tell = fh.tell
                    # Create individual lists of the file's clusters and data we've obtained from the qeueue.
                    clusters, data = zip(*filedb[_file])
                    idx = 0
                    num_clusters = len(clusters)
                    buff = []
                    # For every cluster for this file we've received...
                    while idx < num_clusters:
                        # Create an initial offset using the current index into the cluster array.
                        offset = clusters[idx]
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
                        seek(self.files[_file][1].index(offset) * self.cluster_size, os.SEEK_SET)
                        # Check to see if (initial offset + data length) > size of the file. This
                        # normally occurs because the file's size is not an exact multiple of the
                        # cluster size and thus the final cluster is zero padded. If this is so,
                        # trim off the padding.
                        if tell() + len("".join(buff)) > int(self.files[_file][0]):
                            left = int(self.files[_file][0] - tell())
                            out = "".join(buff)
                            write(out[:left])
                        # Otherwise just append the data.
                        else:
                            write("".join(buff))
                        # Subtract the number of clusters written from the file's remaining clusters list.
                        self.file_progress[_file] -= len(buff)
                        self.bytes_written += len(buff)
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
            for _file in self.residentfiles:
                fh = open(_file, 'wb')
                fh.write(self.residentfiles[_file])
                fh.close()
                self.bytes_written += len(self.residentfiles[_file])
                self.file_queue.put_nowait(_file)
            self.handler.running = False
            self.show_status = False
            self.proc.join()
            return
        except KeyboardInterrupt:
            print 'User cancelled execution...'
            self.show_status = False
            self.handler.running = False
            self.ns.remove(name=self.name)
            return
            
    def show_status_info(self):
        self.clear_screen()
        num_files = len(self.files)
        start_time = int(time())
        while self.show_status:
            sleep(3)
            """
            if len(self.queue) >= 524288:
                self.throttle = True
                sleep(3)
            else:
                self.throttle = False
            """
            duration = int(time()) - start_time
            print("\033[1;0H%s" % "{0} of {1} files remaining {2:<30s}".format(len(self.file_progress), num_files, ''))
            print("\033[2;0H%s" % "Clusters in queue: {0:<30d}".format(len(self.queue)))
            #print("\033[3;0H%s" % "Client CPU usage: {0:<30d}".format(int(get_cpu_percent())))
            print("\033[3;0H%s" % "Total bytes written to disk(MB): {0:<30d}".format(self.bytes_written / MB))
            print("\033[4;0H%s" % "Average write rate: {0} MB/s {1:<30s}".format((self.bytes_written / MB) / (duration), ''))
            print("\033[5;0H%s" % "Duration: {0:02d}:{1:02d}:{2:02d}".format((duration/3600), ((duration/60) % 60), (duration % 60)))
            if self.throttle:
                print("\033[6;0HThrottling...")
            else:
                print("\033[6;0H%s" % "{0:<30s}".format(''))

    """
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
            addstr_stdscr = self.stdscr.addstr
            while self.show_status:
                time.sleep(3)
                if len(self.queue) >= 524288:
                    self.throttle = True
                    time.sleep(3)
                else:
                    self.throttle = False
                cur_write_rate = (process.get_io_counters()[1] / MB)
                duration = int(time.time()) - start_time
                addstr_stdscr(0, 0, "{0} of {1} files remaining {2:<30s}".format(len(self.file_progress), num_files, ''))
                addstr_stdscr(1, 0, "Clusters in queue: {0:<30d}".format(len(self.queue)))
                addstr_stdscr(2, 0, "Client CPU usage: {0:<30d}".format(int(get_cpu_percent())))
                #self.stdscr.addstr(3, 0, "Using {0} MB of {1} MB physical memory | {2} MB physical memory free {3:<20s}".format
                #                      ((get_memory_info()[0] / MB), (total_mem / MB), ((avail_phymem() +
                #                      cached_phymem() + phymem_buffers()) / MB), ''))
                addstr_stdscr(3, 0, "Total bytes written to disk(MB): {0:<30d}".format(cur_write_rate))
                try:
                    addstr_stdscr(4, 0, "Average write rate: {0} MB/s {1:<30s}".format((cur_write_rate / (duration)), ''))
                except:
                    addstr_stdscr(4, 0, "Average write rate: {0} MB/s {1:<30}".format((cur_write_rate / duration), ''))
                #self.stdscr.addstr(6, 0, "Current idle time: {0:02d}:{1:02d}:{2:02d}".format((cur_idle/3600), ((cur_idle/60) % 60), (cur_idle % 60)))
                #self.stdscr.addstr(7, 0, "Total idle time: {0:02d}:{1:02d}:{2:02d}".format((total_idle/3600), ((total_idle/60) % 60), (total_idle % 60)))
                addstr_stdscr(5, 0, "Duration: {0:02d}:{1:02d}:{2:02d}".format((duration/3600), ((duration/60) % 60), (duration % 60)))
                if self.throttle:
                    addstr_stdscr(6, 0, "Throttling...")
                else:
                    addstr_stdscr(6, 0, "{0:<30s}".format(''))
                    self.stdscr.move(6, 0)
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
    """

def main():
    argparser = argparse.ArgumentParser()
    argparser.add_argument('-p', '--path', help = "Root directory for client. Files will be written and processed here. Defaults to the current working directory if no value is specified.", required = False)
    argparser.add_argument('-i', '--id', help = "Unique name/identifier used to register the client with the Pyro nameserver.", required = True)
    argparser.add_argument('-c', '--config', help = "Path to config directory.", required = False)
    argparser.add_argument('-n', '--nameserver', help = "IP/Hostname of Pyro nameserver.", required = True)
    argparser.add_argument('-b', '--bind', help = "The IP/Hostname to bind this daemon to.", required = True)
    args = argparser.parse_args()
    opts = vars(args)
    name = opts['id']
    path = opts['path']
    config_path = opts['config']
    nameserver = opts['nameserver']
    boundhost = opts['bind'] 
    if path == None:
        path = os.path.abspath(os.path.curdir)
    elif not os.path.lexists(path):
        print "Invalid path specified."
        sys.exit(-1)
    if path.endswith(os.path.sep):
        path = path[:-1]
    if config_path == None:
        config_path = os.path.abspath(os.path.curdir) + os.path.sep + 'config'
    elif not os.path.lexists(config_path):
        print "Invalid path specified."
        sys.exit(-1)
    if config_path.endswith(os.path.sep):
        config_path = config[:-1]
    # Start Pyro daemon
    daemon = Pyro4.core.Daemon(host=boundhost)
    ns = Pyro4.naming.locateNS(nameserver)
    client = StreamClient(name=name, path=path, config_path=config_path, ns=ns, daemon=daemon)
    uri = daemon.register(client)
    ns.register(name, uri)
    try:
        daemon.requestLoop()
    except KeyboardInterrupt:
        print 'User aborted'
        ns.remove(name=name)
        daemon.shutdown()
        sys.exit(-1)

if __name__ == "__main__":
	main()
