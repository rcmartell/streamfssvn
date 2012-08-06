import os, shutil
from xml.etree import ElementTree as tree
from pysolr import Solr

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
        self.solr = Solr(url='http://localhost:8983/solr')

    def handler_queue(self, queue):
        while self.running:
            target = queue.get()
            self.process_file(target)
        return

    def process_file(self, target):
        with open(target, 'rb') as fh:
            try:
                self.solr.extract(fh)
            except:
                pass
        for filetype in self.types:
            if os.path.splitext(target)[1][1:].upper() in self.types[filetype]:
                try:
                    if not os.path.exists(self.dirs[filetype] + os.path.sep + os.path.basename(target)):
                        shutil.move(target, self.dirs[filetype])
                        return
                    else:
                        shutil.move(target, self.dirs[filetype] + os.path.sep + "[" + str(self.count) + "]" + os.path.basename(target))
                        self.count += 1
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
