import sys, os, shutil
import random, pickle
from time import ctime
from file_magic import *
import SocketServer
from socket import gethostname
import array

class Stream_Listener(SocketServer.BaseRequestHandler):

    def handle(self):
        self.data = self.request.recv(4096)
        commands = {'set_cluster_size'      :   self.set_cluster_size, 
                    'process_entries'       :   self.process_entries,
                    'setup_clustermap'      :   self.setup_clustermap,
                    'setup_file_progress'   :   self.setup_file_progress,
                    'list_clusters'         :   self.list_clusters,
                    'get_data'              :   self.get_data}
        cmd = self.data.split()
        if len(cmd) == 3:
            commands[cmd[0]](cmd[1], cmd[2])
        elif len(cmd) == 2:
            commands[cmd[0]](cmd[1])
        else:
            commands[cmd[0]]()        
    
    def set_cluster_size(self, size):
        self.server.cluster_size = int(size)

    def process_entries(self):
        self.request.send('ready')
        entry_str = ''
        while True:
            bytes = self.request.recv(4096)
            if bytes:
                entry_str += bytes
            else:
                break
        entries = pickle.loads(entry_str)
        for entry in entries:
            try:
                entry.name = "[" + entry.parent + "]" + entry.name
            except:
                pass
            if entry.real_size == 0:
                if entry.data_size != 0:
                    self.server.files[entry.name] = [entry.data_size, entry.clusters]
                else:
                    self.server.files[entry.name] = [len(entry.clusters) * self.server.cluster_size, entry.clusters]
            else:
                self.server.files[entry.name] = [entry.real_size, entry.clusters]
  
        
    def setup_clustermap(self):
        for k,v in self.server.files.iteritems():
            for c in v[1]:
                self.server.clustermap[c] = k
        self.request.send('ready')
    
    def setup_file_progress(self):
        for file in self.server.files:
            self.server.file_progress[file] = len(self.server.files[file][1])
        self.request.send('ready')
  
    def list_clusters(self):
        clusters = []
        for k,v in self.server.files.iteritems():
            try:
                clusters.extend(v[1])
            except:
                clusters.append(v[1])
        self.request.sendall(pickle.dumps(clusters))
    
        
    def get_data(self):
        arr = array.array("b")
        msg = ''
        self.request.recv_into(msg)
        if msg:
            clusters = list(msg)
        else:
            break
        data = ''
        self.request.recv_into(data)
        for cluster in clusters:
            if cluster in self.server.clustermap:
    		    file = self.server.clustermap[cluster]
    	    else:
    		    continue
            try:
                fh = open(file, 'rb+')
            except:
                fh = open(file, 'wb')
            fh.seek(self.server.cluster_size * self.server.files[file][1].index(cluster), os.SEEK_SET)
            if (fh.tell() + self.server.cluster_size) > int(self.server.files[file][0]):
                left = int(self.server.files[file][0]) - fh.tell()
                fh.write(data[:left])
            else:
                fh.write(data)
            fh.close()
            self.server.file_progress[file] -= 1
            if not self.server.file_progress[file]:
                self.file_complete(file)
            del(self.server.clustermap[cluster])
            if len(self.server.clustermap) == 0:
                break

    def file_complete(self, filename):
        del(self.server.files[filename])
        self.server.magic.process_file(filename)
        
class TCPServer(SocketServer.TCPServer):
    def setup(self):
        self.clustermap = {}
        self.cluster_size = 0
        self.files = {}
        self.magic = File_Magic()
        self.file_progress = {}
        
if __name__ == '__main__':
    try:
	    import psyco
	    psyco.full()
    except:
	    pass
    server = TCPServer((gethostname(), 9999), Stream_Listener)
    server.setup()
    try:
        os.mkdir('Complete')
        os.mkdir('Incomplete')
    except:
        pass
    os.chdir('Incomplete')
    server.serve_forever()
    
