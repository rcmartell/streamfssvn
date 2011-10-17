import sys, os
import magic, threading
import shutil

try:
    import psyco
    psyco.full()
except:
    pass

class FileMagic():
    def __init__(self, path):
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

    def setup_filters(self):
        self.filters = {
            'Video'         :   ['AVI', 'MPEG', 'MPG', 'WMV', 'ASX', 'FLV', 'MPEG2', 'MPEG4', 'RMV',
                                'MOV', 'H.264', 'XVID', 'DIVX', 'MKV'],
            'Image'         :   ['JPG', 'JPEG', 'GIF', 'TIF', 'TIFF', 'PNG', 'BMP', 'RAW', 'TGA', 'PCX'],
            'Audio'         :   ['MP3', 'M4A', 'M4P', 'WMA', 'FLAC', 'AAC', 'AIFF', 'WAV', 'OGG'],
            'Application'   :   ['PE32', 'BIN', 'EXE', 'APP', 'O'],
            'Text'          :   ['TXT', 'XML', 'CHM','CFG', 'CONF', 'RTF', 'DOC', 'XLS', 'DOCX', 'XLSX', 'XLT', 'DTD', 'HTML', 'ASP', 'PHP', 'CSS', 'MHT', 'MHTML', 'HTM', 'PDF'],
            'System'        :   ['DLL', 'INI', 'SYS', 'INF', 'OCX', 'CPA', 'LRC']
        }


    def process_file(self, file):
        self.thread = threading.Thread(target=self.sort_file, args=(file,))
        self.thread.start()
        return

    def sort_file(self, file):
        self.filemagic = magic.file(file)
        category = self.filemagic.split('/')[0]
        if category in self.dirs:
            try:
                shutil.move(file, self.dirs[category])
            except:
                os.remove(self.dirs[category] + os.path.basename(file))
                shutil.move(file, self.dirs[category])
        else:
            for filter in self.filters:
                if os.path.splitext(file)[1][1:].upper() in self.filters[filter]:
                    try:
                        shutil.move(file, self.dirs[filter])
                    except:
                        os.remove(self.dirs[filter] + os.path.basename(file))
                        shutil.move(file, self.dirs[filter])
                    return
            try:
                shutil.move(file, self.dirs['Other'])
            except:
                os.remove(self.dirs['Other'] + os.path.basename(file))
                shutil.move(file, self.dirs['Other'])
        return
