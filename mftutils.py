from mftparser import MFTParser
import time

MFT_ENTRY_SIZE = 0x400  

def getFiletypeStats(parser):
        filestats = {'image' : [], 'binaries' : [], 'video' : [], 'audio' : [], 'text' : [], 'system' : [], 'compressed' : [], 'other' : []}
        video = ['AVI', 'MPEG', 'MPG', 'WMV', 'ASX', 'FLV', 'MPEG2', 'MPEG4', 'RMV', 'MOV', 'H.264', 'FFMPEG', 'XVID', 'DIVX', 'MKV']
        image = ['JPG', 'JPEG', 'GIF', 'TIF', 'TIFF', 'PNG', 'BMP', 'RAW', 'TGA', 'PCX']
        audio = ['MP3', 'M4A', 'M4P', 'WMA', 'FLAC', 'AAC', 'AIFF', 'WAV', 'OGG']
        binaries = ['BIN', 'EXE', 'APP', 'O']
        text = ['TXT', 'XML', 'CHM','CFG', 'CONF', 'RTF', 'DOC', 'XLS', 'DOCX', 'XLSX', 'XLT', 'DTD', 'JS', 'JAVA', 'C', 'H', 'PY',
                'PL', 'CPP', 'XAML', 'VB', 'HLP', 'SH', 'HTML', 'ASP', 'PHP', 'CSS', 'MHT', 'MHTML', 'HTM', 'PDF']
        system = ['DLL', 'INI', 'SYS', 'INF', 'OCX', 'CPA', 'LRC']
        compressed = ['GZ', 'ZIP', 'BZ', '7Z', 'ACE', 'RAR', 'Z']
        filetypes = video, image, audio, binaries, text, system, compressed
        types = ['video', 'image', 'audio', 'binaries', 'text', 'system', 'compressed']
        for entry in parser.entries:
            try:
                ext = entry.name.split('.')[-1]
            except:
                filestats['other'].append(entry.name)
                continue
            i = 0
            for ftype in filetypes:
                if ext.upper() in ftype:
                    filestats[types[i]].append(entry.name)
                    break
                i += 1
            else:
                filestats['other'].append(entry.name)
        print "Number of files: %i" % len(parser.entries)
        print "video      : %i" % len(filestats['video'])
        print "images     : %i" % len(filestats['image'])
        print "audio      : %i" % len(filestats['audio'])
        print "binaries   : %i" % len(filestats['binaries'])
        print "text       : %i" % len(filestats['text'])
        print "compressed : %i" % len(filestats['compressed'])
        print "system     : %i" % len(filestats['system'])
        print "other      : %i" % len(filestats['other'])


def print_header(parser):
    print "*****************HEADER INFO*****************"
    print "Entry:                           %i" % parser.header.entry_num
    print "$Logfile seq number:             %i" % parser.header.lsn
    print "MFT Base Record:                 %i" % parser.header.mft_base
    print "Allocation status:              ",
    if parser.header.flags & 0x01:
        print "Allocated"
    else:
        print "Unallocated/Deleted"
    print "Links:                           %i" % parser.header.lnk_cnt
    print ''

def print_std_info(parser):
    print "****************STANDARD INFO****************"
    print "Flags:   ",
    print parser.std_info.flags
    print "Created:             %s" % parser.std_info.ctime
    print "File Modified:       %s" % parser.std_info.mtime
    print "Accessed:            %s" % parser.std_info.atime
    print ''

def print_filename(parser):
    print "****************FILENAME INFO****************"
    print "Flags:   ",
    print parser.filename.flags
    print "Entry Name:          %s" % parser.filename.name
    print "Parent MFT Entry:    %s" % parser.filename.parent
    print "Created:             %s" % parser.filename.ctime
    print "File Modified:       %s" % parser.filename.mtime
    print "Accessed:            %s" % parser.filename.atime
    print "Allocated size:      %i" % parser.filename.alloc_size
    print "Actual size:         %i" % parser.filename.real_size
    print ''

def print_object_id(parser):
    print "******************OBJECT ID******************"
    print "Object ID: %s" % parser.object_id.object_id.upper()
    print ''

def print_idx_root(parser):
    print "*****************INDEX ROOT**************"
    print parser.idx_root.idx_entries
    print ''


def print_idx_alloc(parser):
    print "*****************INDEX ALLOCATION**************"
    print parser.idx_alloc.idx_entries
    print ''


def print_data(data, clusters, start_vcn, end_vcn, show_clusters=False):
    print "******************DATA INFO******************"
    print "Attribute ID:                    %i" % data.attr_id
    print "Attribute Name:                  %s" % data.name
    print "Flags:                           %s" % data.flags
    print "Allocated size:                  %i" % data.alloc_size
    print "Actual size:                     %i" % data.data_size
    print "Residence:                      ",
    if data.nonresident:
        print "Nonresident"
    else:
        print "Resident"
    if data.start_vcn != None:
        print "First Data VCN:                  %i" % start_vcn
    if data.end_vcn != None:
        print "Last Data VCN:                   %i" % end_vcn
    print "File fragmented:                 %s" % data.file_fragmented
    if show_clusters and data.clusters != None:
        width = 0
        print "Data Clusters: "
        for cluster in clusters:
            if width < 7:
                print "%s" % cluster,
                width += 1
            else:
                print cluster
                width = 0
    if data.res_data != None:
        print "ADS Data: "
        print data.res_data
    print ''

def print_fsdata(parser):
    print "******************FS INFO******************"
    print "Volume Type: NTFS"
    print "Volume Serial Number: %s" % str(parser.serial_num)[2:-1].upper()
    print "Volume Size: %i" % parser.num_bytes
    print "Sector Size: %i" % parser.sector_size
    print "Cluster Size: %i" % parser.cluster_size
    print "Number of Sectors: %i" % parser.num_sectors
    print "Number of Clusters: %i" % parser.num_clusters
    print "MFT Entry Size(Bytes): %i" % MFT_ENTRY_SIZE
    print "$MFT Offset(Bytes): %i" % parser.mft_base_offset
    print "$MFT Offset(Clusters): %i" % (parser.mft_base_offset / parser.cluster_size)
    print "$MFTMIR Offset(Bytes): %i" % parser.mft_mir_base_offset
    print "$MFTMIR Offset(Clusters): %i" % (parser.mft_mir_base_offset / parser.cluster_size)

def cluster_to_file(parser, cluster):
    for entry in parser.entries:
        if int(cluster) == entry.entry_num:
            print "Cluster: %s => MFT Entry: %s => File: %s" % (cluster, entry.entry_num, entry.name)
            return
        if int(cluster) in entry.clusters:
            print "Cluster: %s => File: %s => MFT Entry: %s" % (cluster, entry.name, entry.entry_num)
            return
    else:
        print "Cluster: %s unallocated" % cluster

def search(parser, name):
    for entry in parser.entries:
        if entry.name.__contains__(name):
            print "MFT Entry: %d" % entry.entry_num
            print "Entry Name: %s" % entry.name


if __name__ == "__main__":
    import argparse, sys
    argparser = argparse.ArgumentParser(description="""
    Parses the MFT of an NTFS filesystem. The data returned depends on the flags selected by the user. Optional functionality similar to Sleuthkit's fsstat/istat is possible, as well as a tentative count of various file-types found throughout the system. Note: When using this option, the file-type is determined exclusively by extension, so counts may not truly reflect the contents of the system. The command-line functions are only "extra-functionality", as the main purpose of this tool is to be used by an "image reader", to parse and return serializable MFT entry objects, each representing a unique file on the file-system. Each object can be used, in conjunction with its raw data blocks, to recreate the file it represents on the fly.
    """)
    argparser.add_argument('-t', '--target', help="Target image/drive to be parsed.", required=True)
    group = argparser.add_mutually_exclusive_group(required=True)
    group.add_argument('-e', '--entry', type=int, help="Get basic MFT entry data for supplied entry number. Similar to Sleuthkit's istat sans datarun info for ease of viewing. See -d/--data for datarun listings.")
    group.add_argument('-d', '--data', type=int, help="Get data blocks belonging to file in specified MFT entry.")
    group.add_argument('-f', '--files', help="Get a summary count of various file-types found on the filesystem.", action='store_true')
    group.add_argument('-i', '--info', help="Get basic volume information. Similar to Sleuthkit's fsstat.", action='store_true')
    group.add_argument('-s', '--search', help="Find MFT Entry number(s) belonging to files whose names contain the supplied string.")
    group.add_argument('-c', '--cluster', help="Map supplied cluster to it's owning file if allocated.")
    args = argparser.parse_args()
    parser = MFTParser(args.target)
    parser.setup_mft_data()
    opts = vars(args)

    if opts['entry'] != None or opts['data'] != None:
        try:
            entry_num = int(opts['entry'])
        except:
            entry_num = int(opts['data'])
        parser.parse_mft(start=entry_num, end=entry_num, fullParse=True, cleanup=False, getFullPaths=False, getIDXEntries=True)
    if opts['entry'] != None:
        if not hasattr(parser, 'data'):
            print "Invalid MFT Entry"
            sys.exit(-1)
        if hasattr(parser, 'header') and parser.header != None:
            print_header(parser)
        if hasattr(parser, 'std_info') and parser.std_info != None:
            print_std_info(parser)
        if hasattr(parser, 'filename') and parser.filename != None:
            print_filename(parser)
        if hasattr(parser, 'object_id'):
            print_object_id(parser)
        if hasattr(parser, 'idx_root'):
            print_idx_root(parser)
        if hasattr(parser, 'idx_alloc'):
            print_idx_alloc(parser)
        if len(parser.data):
            start_vcn = parser.data[0].start_vcn
            end_vcn = 0
            clusters = []
            for i in range(len(parser.data)):
                if parser.data[i].start_vcn != None and parser.data[i].start_vcn < start_vcn:
                    start_vcn = parser.data[i].start_vcn
                if parser.data[i].end_vcn > end_vcn:
                    end_vcn = parser.data[i].end_vcn
            print_data(parser.data[0], clusters, start_vcn, end_vcn)
    elif opts['data'] != None:
        if not hasattr(parser, 'data'):
            print "Invalid MFT Entry"
            sys.exit(-1)
        if hasattr(parser, 'header') and parser.header != None:
            print_header(parser)
        if hasattr(parser, 'std_info') and parser.std_info != None:
            print_std_info(parser)
        if hasattr(parser, 'filename') and parser.filename != None:
            print_filename(parser)
        if hasattr(parser, 'object_id'):
            print_object_id(parser)
        if hasattr(parser, 'idx_root'):
            print_idx_root(parser)
        if hasattr(parser, 'idx_alloc'):
            print_idx_alloc(parser)
        if len(parser.data):
            start_vcn = parser.data[0].start_vcn
            end_vcn = 0
            clusters = []
            for i in range(len(parser.data)):
                if parser.data[i].start_vcn != None and parser.data[i].start_vcn < start_vcn:
                    start_vcn = parser.data[i].start_vcn
                if parser.data[i].end_vcn > end_vcn:
                    end_vcn = parser.data[i].end_vcn
                if hasattr(parser.data[i], 'clusters'):
                    clusters.extend(parser.data[i].clusters)
                res_data = parser.data[i].res_data
            print_data(parser.data[0], clusters, start_vcn, end_vcn, True)
    elif opts['files']:
        print time.ctime()
        parser.parse_mft(fullParse=True, quickstat=True, getIDXEntries=False, getFullPaths=False)
        getFiletypeStats(parser)
        print time.ctime()
    elif opts['info']:
        print_fsdata(parser)
    """
    elif opts['lookup']:
        parser.parse_mft(fullParse=True, quickstat=True, getFullPaths=True)
        search(parser, opts['lookup'])
    elif opts['cluster']:
        parser.parse_mft(fullParse=True, quickstat=False, getFullPaths=True)
        cluster_to_file(parser, opts['cluster'])
    """
