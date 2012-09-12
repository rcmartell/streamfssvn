import os, shutil
from multiprocessing import Process, Queue
from xml.etree import ElementTree as tree
from textindexer import TextIndexer

CONFIG_PATH = 'config'
CONFIG_FILE = 'config.xml'
LOG_FILE = 'handler.log'

class FileHandler():
    def __init__(self, path):
        self.log = open(path + os.path.sep + LOG_FILE, 'wb')
        with open(path + os.path.sep + CONFIG_PATH + os.path.sep + CONFIG_FILE) as fh:
            config = tree.fromstring(fh.read())
        self.types, self.dirs = {}, {}
        for elem in config.getchildren()[0].findall('type'):
            if elem.get('include') == 'true':
                filetype = elem.get('name')
                self.dirs[filetype] = '{0}{1}Complete{1}{2}'.format(path, os.path.sep, elem.get('directory'))
                os.mkdir(self.dirs[filetype])
                with open(path + os.path.sep + CONFIG_PATH + os.path.sep + elem.text) as fh:
                    self.types[filetype] = fh.read().split()
        self.running = True
        #self.indexer_queue = Queue()
        #self.indexer = TextIndexer()
        #self.proc = Process(target=self.indexer.init_threads, args=(self.indexer_queue,))
        #self.proc.daemon = True
        #self.proc.start()

    def handler_queue(self, queue):
        while self.running or not queue.empty():
            target = queue.get()
            self.process_file(target)
        #self.indexer.running = False
        return

    def process_file(self, target):
        ext = os.path.splitext(target)[1][1:].upper()
        basename = os.path.basename(target)
        for filetype in self.types:
            if ext in self.types[filetype]:
                try:
                    path = self.dirs[filetype] + os.path.sep + basename
                    shutil.move(target, path)
                    #self.indexer_queue.put_nowait(path)
                except:
                    self.log.write("Error moving file: {0}\n".format(target))
                return
        else:
            try:
                path = self.dirs['misc'] + os.path.sep + basename
                shutil.move(target, path)
            except:
                self.log.write("Error moving file: {0}\n".format(target))
            return
