import os, shutil
from multiprocessing import Process, Queue
from xml.etree import ElementTree as tree
from textindexer import TextIndexer

class FileHandler():
    def __init__(self, path):
        self.count = 0
        self.path = path
        self.errfile = open(self.path + os.path.sep + 'filehandler.err', 'wb')
        with open(self.path + os.path.sep + 'config.xml') as fh:
            config = tree.fromstring(fh.read())
        self.types = {}
        self.dirs = {}
        for elem in config.getchildren()[0].findall('type'):
            if elem.get('include') == 'true':
                filetype = elem.get('name')
                self.dirs[filetype] = '{0}{1}Complete{1}{2}'.format(self.path, os.path.sep, elem.get('directory'))
                os.mkdir(self.dirs[filetype])
                with open(self.path + os.path.sep + elem.text) as fh:
                    self.types[filetype] = fh.read().split()
        os.mkdir('{0}{1}Complete{1}{2}'.format(self.path, os.path.sep, 'Misc'))
        self.running = True
        self.queue = Queue()
        self.indexer = TextIndexer()
        self.proc = Process(target=self.indexer.index_queue, args=(self.queue,))
        self.proc.daemon = True
        self.proc.start()

    def handler_queue(self, queue):
        while self.running:
            target = queue.get()
            self.process_file(target)
        while len(queue):
            target = queue.get()
            self.process_file(target)
        self.indexer.running = False
        self.proc.join()
        return

    def process_file(self, target):
        for filetype in self.types:
            if os.path.splitext(target)[1][1:].upper() in self.types[filetype]:
                try:
                    if not os.path.exists(self.dirs[filetype] + os.path.sep + os.path.basename(target)):
                        path = self.dirs[filetype] + os.path.sep + os.path.basename(target)
                    else:
                        path = self.dirs[filetype] + os.path.sep + "[" + str(self.count) + "]" + os.path.basename(target)
                        self.count += 1
                    shutil.move(target, path)
                    self.queue.put_nowait(path)
                    return
                except:
                    self.errfile.write("Error moving file: {0}\n".format(target))
                    return
        else:
            try:
                if not os.path.exists(self.dirs['Misc'] + os.path.sep + os.path.basename(target)):
                    shutil.move(target, self.dirs['Misc'])
                    return
                else:
                    shutil.move(target, self.dirs['Misc'] + os.path.sep + "[" + str(self.count) + "]" + os.path.basename(target))
                    self.count += 1
                    return
            except:
                self.errfile.write("Error moving file: {0}\n".format(target))
                return
