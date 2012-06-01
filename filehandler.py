import os, shutil, json

class FileHandler():
    def __init__(self, path):
        self.count = 0
        self.errfile = open(path + os.path.sep + "filehandler.err", "wb")
        config = json.load(open('config.json'))
        for directory in config['Directories']:
            self.directories[directory] = "{0}{1}Complete{1}{2}".format(path, os.path.sep, config['Directory'][directory])
        for directory in self.directories.values():
            try:
                os.mkdir(directory)
            except:
                pass
        for idx in range(len(config['Filetypes'])):
            self.filters[config['Filetypes'][idx].keys()[0]] = config['Filetypes'][idx].values()[0]
        self.running = True

    def processFiles(self, queue):
        while self.running:
            _file = queue.get()
            self.processFile(_file)
        return

    def processFile(self, _file):
        for _filter in self.filters:
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
