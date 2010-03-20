import sys, os
import magic
import shutil


class File_Magic():
    def __init__(self):
        self.dirs = \
        {
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
        for val in self.dirs.values():
            try:
                os.mkdir(val)
            except:
                pass
        self.setup_filters()

	def process_file(self, file):
	    self.filemagic = magic.file(file)
	    category, type = self.filemagic.split('/')
	    if category in self.dirs:
	        shutil.move(file, self.dirs[category])
	    else:
	        for filter in self.filters:
	            if os.path.splitext(file)[1][1:].upper() in self.filters[filter]:
	                shutil.move(file, self.dirs[filter])
	                return
	        shutil.move(file, self.dirs['other'])
	    
    def setup_filters(self):
        self.filters = \
        {
            'video'         :   ['AVI', 'MPEG', 'WMV', 'ASX', 'FLV', 'MPEG2', 'MPEG4',
                                'MOV', 'H.264', 'FFMPEG', 'XVID', 'DIVX', 'MKV', 'NTSC'],
            'pdf'           :   ['PDF'],
            'image'         :   ['JPG', 'JPEG', 'GIF', 'TIF', 'TIFF', 'PNG', 'BMP', 'RAW', 'TGA', 'PCX'],
            'audio'         :   ['MP3', 'MP4A', 'MP4P', 'WMA', 'FLAC', 'AAC', 'AIFF', 'WAV', 'OGG'],
            'application'   :   ['data', 'executable', 'ELF', 'PE32', 'BIN'],
            'text'          :   ['ASCII', 'Little-endian UTF-16 Unicode text', 'Microsoft Office',
                                'Unicode', 'CDF V2 Document', 'TXT', 'XML', 'CHM',
                                'CFG', 'CONF', 'RTF', 'DOC', 'XLS', 'DOCX', 'XLSX', 'XLT', 'DTD'],
            'html'          :   ['HTML', 'ASP', 'PHP', 'CSS'],
            'system'        :   ['DLL', 'INI', 'SYS', 'INF', 'OCX', 'CPA', 'LRC']
        }

