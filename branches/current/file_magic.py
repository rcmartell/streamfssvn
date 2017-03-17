import sys, os, server_stats
import magic, threading
import shutil, Pyro.core, Pyro.util

try:
    import psyco
    psyco.full()
except:
    pass

class File_Magic():
    def __init__(self):
        self.dirs = {
            'Image'         : '../Complete/Image//',
            'PDF'           : '../Complete/PDF//',
            'Video'         : '../Complete/Video//',
            'Application'   : '../Complete/Application//',
            'System'        : '../Complete/System//',
            'Audio'         : '../Complete/Audio//',
            'Text'          : '../Complete/Text//',
            'HTML'          : '../Complete/HTML//',
            'Other'         : '../Complete/Other//'
        }
        self.filters = {
            'Video'         :   ['AVI', 'MPEG', 'MPG', 'WMV', 'ASX', 'FLV', 'MPEG2', 'MPEG4', 'RMV',
                                'MOV', 'H.264', 'XVID', 'DIVX', 'MKV'],
            'PDF'           :   ['PDF'],
            'Image'         :   ['JPG', 'JPEG', 'GIF', 'TIF', 'TIFF', 'PNG', 'BMP', 'RAW', 'TGA', 'PCX'],
            'Audio'         :   ['MP3', 'M4A', 'M4P', 'WMA', 'FLAC', 'AAC', 'AIFF', 'WAV', 'OGG'],
            'Application'   :   ['PE32', 'BIN', 'EXE', 'APP', 'O'],
            'Text'          :   ['TXT', 'XML', 'CHM','CFG', 'CONF', 'RTF', 'DOC', 'XLS', 'DOCX', 'XLSX', 'XLT', 'DTD'],
            'HTML'          :   ['HTML', 'ASP', 'PHP', 'CSS', 'MHT', 'MHTML', 'HTM'],
            'System'        :   ['DLL', 'INI', 'SYS', 'INF', 'OCX', 'CPA', 'LRC']
        }
        for val in self.dirs.values():
            try:
                os.mkdir(val)
            except:
                pass
        self.server_stats = server_stats.Server_Stats()

    def process_file(self, file):
        self.thread = threading.Thread(target=self.sort_file, args=(file,))
        self.thread.start()
        return

    def sort_file(self, file):
        self.filemagic = magic.file(file)
        category = self.filemagic.split('/')[0]
        size = os.stat(file).st_size
        if category in self.dirs:
            try:
                shutil.move(file, self.dirs[category])
            except:
                os.remove(self.dirs[category] + file)
                shutil.move(file, self.dirs[category])
            self.server_stats.addFile(category, size)
        else:
            for filter in self.filters:
                if os.path.splitext(file)[1][1:].upper() in self.filters[filter]:
                    try:
                        shutil.move(file, self.dirs[filter])
                    except:
                        os.remove(self.dirs[filter] + file)
                        shutil.move(file, self.dirs[filter])
                    self.server_stats.addFile(filter, size)
                    return
            try:
                shutil.move(file, self.dirs['Other'])
            except:
                os.remove(self.dirs['Other'] + file)
                shutil.move(file, self.dirs['Other'])
            self.server_stats.addFile("Other", size)
        return
