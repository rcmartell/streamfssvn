import json, os, sys
from mft import FILE_RECORD
from mftparser import MFTParser

class SummaryWriter():
    def __init__(self, path):
        self.fh = open(path, 'wb')
        self.fh.write( "{ \"Summary\" : [" + "\n")

    def writeEntry(self, entry, lastEntry=False):
        num = entry.entry_num
        name = unicode(os.path.basename(entry.name).replace('\x00','').replace("\\", "\\\\").replace('\n', "").replace("\"", "'").replace('\r', ""), errors="ignore")
        path = unicode(os.path.dirname(entry.name).replace('\x00','').replace("\\", "\\\\").replace('\n', "").replace("\"", "'").replace('\r', ""), errors="ignore")
        ctime = entry.ctime
        mtime = entry.mtime
        atime = entry.atime
        size = entry.size
        clusters = entry.clusters
        if entry.res_data != None:
            res_data = unicode(entry.res_data.replace('\x00', '').replace('\n', "").replace("\"", "'").replace('\r', "").replace("\\", "\\\\"), errors="ignore")
        else:
            res_data = ""
        if not lastEntry:
            entrystr = "{ \"%s\" : [ \"%s\", \"%s\", \"%s\", \"%s\", \"%s\", \"%s\", \"%s\" , \"%s\" ] },\n" % (num, name, path, ctime, mtime, atime, size, "".join(str(clusters)[1:-1]), res_data)
            self.fh.write(entrystr)
        else:
            entrystr = "{ \"%s\" : [ \"%s\", \"%s\", \"%s\", \"%s\", \"%s\", \"%s\",  \"%s\" , \"%s\" ] } ] }\n" % (num, name, path, ctime, mtime, atime, size, "".join(str(clusters)[1:-1]), res_data)
            self.fh.write(entrystr)
            self.fh.close()


