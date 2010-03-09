import sys, os
import magic
import shutil


class File_Magic():
    def __init__(self):
        self.dirs = \
        {
            'imgdir' : '../Complete/img//',
            'pdfdir' : '../Complete/pdf//',
            'viddir' : '../Complete/vid//',
            'bindir' : '../Complete/bin//',
            'sysdir' : '../Complete/sys//',
            'musicdir' : '../Complete/music//',
            'txtdir' : '../Complete/txt//',
            'htmldir' : '../Complete/html//',
            'otherdir' : '../Complete/other//'
        }
        for val in self.dirs.values():
            try:
                os.mkdir(val)
            except:
                pass
        self.setup_filters()

    def process_file(self, file):
        self.filemagic = magic.file(file)
        ext = os.path.splitext(file)[1][1:].upper()
        for filter in self.filters:
            if self.filemagic.split()[0] in self.filters[filter] or ext in self.filters[filter]:
                if filter == 'bin' and ext in self.filters['sys']:
                    shutil.move(file, self.dirs['sysdir'])
                else:
                    shutil.move(file, self.dirs['%sdir' % filter])
                return
        shutil.move(file, self.dirs['otherdir'])

    def setup_filters(self):
        self.filters = \
        {
            'vid' : ['AVI', 'MPEG', 'WMV', 'ASX', 'FLV', 'MPEG2', 'MPEG4',
                    'MOV', 'H.264', 'FFMPEG', 'XVID', 'DIVX', 'MKV', 'NTSC'],
            'pdf' : ['PDF'],
            'img' : ['JPG', 'JPEG', 'GIF', 'TIF', 'TIFF', 'PNG', 'BMP', 'RAW', 'TGA', 'PCX'],
            'music':['MP3', 'MP4A', 'MP4P', 'WMA', 'FLAC', 'AAC', 'AIFF', 'WAV', 'OGG'],
            'bin' : ['data', 'executable', 'ELF', 'PE32', 'BIN'],
            'txt' : ['ASCII', 'Little-endian UTF-16 Unicode text', 'Microsoft Office',
                    'Unicode', 'CDF V2 Document', 'TXT', 'XML', 'CHM',
                    'CFG', 'CONF', 'RTF', 'DOC', 'XLS', 'DOCX', 'XLSX', 'XLT', 'DTD'],
            'html': ['HTML', 'ASP', 'PHP', 'CSS'],
            'sys' : ['DLL', 'INI', 'SYS', 'INF', 'OCX', 'CPA', 'LRC']
        }

