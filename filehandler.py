import os, shutil
from xml.etree import ElementTree as tree

class FileHandler():
    def __init__(self, path):
        self.count = 0
        self.path = path
        with open('{0}{1}config.xml'.format(self.path, os.path.sep)) as fh:
            config = tree.fromstring(fh.read())
        self.types = {}
        self.dirs = {}
        os.chdir('{0}{1}Complete'.format(self.path, os.path.sep))
        for elem in config.getchildren()[0].findall('type'):
            if elem.get('include') == 'true':
                filetype = elem.get('name')
                self.dirs[filetype] = elem.get('directory')
                try:
                    os.mkdir(self.dirs[filetype])
                except:
                    pass
                with open(elem.text) as fh:
                    self.types[filetype] = fh.read().split()
        self.running = True

    def handler_queue(self, queue):
        while self.running:
            target = queue.get()
            self.process_file(target)
        return

    def process_file(self, target):
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
