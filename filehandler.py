import os, shutil, json, pysolr

class FileHandler():
    def __init__(self, path):
        self.count = 0
        self.errfile = open(path + os.path.sep + "filehandler.err", "wb")
        self.index = []
        self.directories = {}
        self.filters = {}
        self.solr = pysolr.Solr("http://localhost:8983/solr")
        config = json.load(open(path + os.path.sep + 'config.json'))
        for directory in config['Directories']:
            self.directories[directory] = "{0}{1}Complete{1}{2}".format(path, os.path.sep, config['Directory'][directory])
        for directory in self.directories.values():
            try:
                os.mkdir(directory)
            except:
                pass
        os.mkdir("Other")
        for idx in range(len(config['Filetypes'])):
            self.filters[config['Filetypes'][idx].keys()[0]] = config['Filetypes'][idx].values()[0]
        for val in config['Index']:
            for key in self.filters:
                if val == key:
                    self.index.append(self.filters[key])
        self.running = True

    def processFiles(self, queue):
        while self.running:
            _file = queue.get()
            self.processFile(_file)
        return

    def processFile(self, _file):
        for _filter in self.filters:
            if os.path.splitext(_file)[1][1:].upper() in self.index:
                try:
                    self.solr.extract(open(_file), extractOnly = False)
                except:
                    pass
            if os.path.splitext(_file)[1][1:].upper() in self.filters[_filter]:
                try:
                    if not os.path.exists(self.directories[_filter] + os.path.sep + os.path.basename(_file)):
                        shutil.move(_file, self.directories[_filter])
                        return
                    else:
                        shutil.move(_file, self.directories[_filter] + os.path.sep + "[" + str(self.count) + "]" + os.path.basename(_file))
                        self.count += 1
                        return
                except:
                    self.errfile.write("Error moving file: {0}\n".format(_file))
                    return
        else:
            try:
                if not os.path.exists(self.directories['Other'] + os.path.sep + os.path.basename(_file)):
                    shutil.move(_file, self.directories['Other'])
                    return
                else:
                    shutil.move(_file, self.directories['Other'] + os.path.sep + "[" + str(self.count) + "]" + os.path.basename(_file))
                    self.count += 1
                    return
            except:
                self.errfile.write("Error moving file: {0}\n".format(_file))
                return
