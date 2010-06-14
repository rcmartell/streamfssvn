import sys, os
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
            'image'         : '../Complete/image//',
            'pdf'           : '../Complete/pdf//',
            'video'         : '../Complete/video//',
            'application'   : '../Complete/application//',
            'system'        : '../Complete/system//',
            'audio'         : '../Complete/audio//',
            'text'          : '../Complete/text//',
            'html'          : '../Complete/html//',
            'other'         : '../Complete/other//'
        }
        self.filters = {
            'video'         :   ['AVI', 'MPEG', 'MPG', 'WMV', 'ASX', 'FLV', 'MPEG2', 'MPEG4', 'RMV',
                                'MOV', 'H.264', 'XVID', 'DIVX', 'MKV'],
            'pdf'           :   ['PDF'],
            'image'         :   ['JPG', 'JPEG', 'GIF', 'TIF', 'TIFF', 'PNG', 'BMP', 'RAW', 'TGA', 'PCX'],
            'audio'         :   ['MP3', 'M4A', 'M4P', 'WMA', 'FLAC', 'AAC', 'AIFF', 'WAV', 'OGG'],
            'application'   :   ['PE32', 'BIN', 'EXE', 'APP', 'O'],
            'text'          :   ['TXT', 'XML', 'CHM','CFG', 'CONF', 'RTF', 'DOC', 'XLS', 'DOCX', 'XLSX', 'XLT', 'DTD'],
            'html'          :   ['HTML', 'ASP', 'PHP', 'CSS', 'MHT', 'MHTML', 'HTM'],
            'system'        :   ['DLL', 'INI', 'SYS', 'INF', 'OCX', 'CPA', 'LRC']
        }
        for val in self.dirs.values():
            try:
                os.mkdir(val)
            except:
                pass

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
                os.remove(self.dirs[category] + file)
                shutil.move(file, self.dirs[category])
        else:
            for filter in self.filters:
                if os.path.splitext(file)[1][1:].upper() in self.filters[filter]:
                    try:
                        shutil.move(file, self.dirs[filter])
                        return
                    except:
                        os.remove(self.dirs[filter] + file)
                        shutil.move(file, self.dirs[filter])
                        return
            try:
                shutil.move(file, self.dirs['other'])
            except:
                os.remove(self.dirs['other'] + file)
                shutil.move(file, self.dirs['other'])
        return
