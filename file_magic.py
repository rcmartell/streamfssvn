import sys, os
import magic
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
            'video'         :   ['AVI', 'MPEG', 'WMV', 'ASX', 'FLV', 'MPEG2', 'MPEG4', 'RMV',
                                'MOV', 'H.264', 'FFMPEG', 'XVID', 'DIVX', 'MKV', 'NTSC', 'PAL'],
            'pdf'           :   ['PDF'],
            'image'         :   ['JPG', 'JPEG', 'GIF', 'TIF', 'TIFF', 'PNG', 'BMP', 'RAW', 'TGA', 'PCX'],
            'audio'         :   ['MP3', 'MP4A', 'MP4P', 'WMA', 'FLAC', 'AAC', 'AIFF', 'WAV', 'OGG'],
            'application'   :   ['data', 'executable', 'ELF', 'PE32', 'BIN', 'EXE', 'APP'],
            'text'          :   ['ASCII', 'Little-endian UTF-16 Unicode text', 'Microsoft Office',
                                'Unicode', 'CDF V2 Document', 'TXT', 'XML', 'CHM',
                                'CFG', 'CONF', 'RTF', 'DOC', 'XLS', 'DOCX', 'XLSX', 'XLT', 'DTD'],
            'html'          :   ['HTML', 'ASP', 'PHP', 'CSS', 'MHT', 'MHTML'],
            'system'        :   ['DLL', 'INI', 'SYS', 'INF', 'OCX', 'CPA', 'LRC']
        }
        for val in self.dirs.values():
            try:
                os.mkdir(val)
            except:
                pass

    def process_file(self, file):
        self.filemagic = magic.file(file)
        category = self.filemagic.split('/')[0]
        try:
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
        except Exception, x:
            print ''.join(Pyro.util.getPyroTraceback(x))
