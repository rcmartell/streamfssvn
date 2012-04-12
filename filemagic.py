import os, shutil

class FileMagic():
    def __init__(self, path):
        self.count = 0
        self.fh = open(path + "/filemagicLog", "wb")
        self.dirs = {
            'Image'         : '%s/Complete/Image/' % path,
            'Video'         : '%s/Complete/Video/' % path,
            'Application'   : '%s/Complete/Application/' % path,
            'System'        : '%s/Complete/System/' % path,
            'Audio'         : '%s/Complete/Audio/' % path,
            'Text'          : '%s/Complete/Text/' % path,
            'Other'         : '%s/Complete/Other/' % path
        }
        for val in self.dirs.values():
            try:
                os.mkdir(val)
            except:
                pass
        self.setup_filters()
        self.running = True

    def setup_filters(self):
        self.filters = {
            'Video'         :   ['AVI', 'MPEG', 'MPG', 'WMV', 'ASX', 'FLV', 'MPEG2', 'MPEG4', 'RMV',
                                'MOV', 'H.264', 'XVID', 'DIVX', 'MKV'],
            'Image'         :   ['JPG', 'JPEG', 'GIF', 'TIF', 'TIFF', 'PNG', 'BMP', 'RAW', 'TGA', 'PCX'],
            'Audio'         :   ['MP3', 'M4A', 'M4P', 'WMA', 'FLAC', 'AAC', 'AIFF', 'WAV', 'OGG'],
            'Application'   :   ['PE32', 'BIN', 'EXE', 'APP', 'O'],
            'Text'          :   ['TXT', 'XML', 'CHM','CFG', 'CONF', 'RTF', 'DOC', 'XLS', 'DOCX', 'XLSX', 'XLT', 'DTD', 'HTML', 'ASP', 'PHP', 'CSS', 'MHT', 'MHTML', 'HTM', 'PDF', 'JAVA', 'LOG', 'PS', 'CSV', 'TSV'],
            'System'        :   ['DLL', 'INI', 'SYS', 'INF', 'OCX', 'CPA', 'LRC']
        }


    #def process_file(self, file):
    #    self.queue.put(file)
    #    return

    def spin_wait(self, queue):
        while self.running:
            f = queue.get()
            self.sort_file(f)
        return


    def sort_file(self, f):
        for _filter in self.filters:
            try:
                if os.path.splitext(f)[1][1:].upper() in self.filters[_filter]:
                    try:
                        shutil.move(f, self.dirs[_filter])
                    except:
                        try:
                            shutil.move(f, self.dirs[_filter] + "[" + str(self.count) + "]" + os.path.basename(f))
                            self.count += 1
                        except:
                            self.fh.write("Error moving file: %s\n" % f)
                            pass
                    return
            except:
                try:
                    shutil.move(f, self.dirs['Other'])
                except:
                    try:
                        shutil.move(f, self.dirs['Other'] + "[" + str(self.count) + "]" + os.path.basename(f))
                        self.count += 1
                    except:
                        self.fh.write("Error moving file: %s\n" % f)
                        pass
                return
        try:
            shutil.move(f, self.dirs['Other'])
        except:
            try:
                shutil.move(f, self.dirs['Other'] + "[" + str(self.count) + "]" + os.path.basename(f))
                self.count += 1
            except:
                self.fh.write("Error moving file: %s\n" % f)
                pass
        return
