#!/usr/bin/python
from mftparser import MFTParser
from summarywriter import SummaryWriter

MFT_ENTRY_SIZE = 0x400


def get_filesystem_summary(parser, path):
    summary = SummaryWriter(path)
    for idx in range(len(parser.entries) - 1):
        summary.writeEntry(parser.entries[idx], False)
    summary.writeEntry(parser.entries[-1], True)


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
    if parser.std_info.sid != None:
        print "Security ID: %s" % str(parser.std_info.sid)
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
    if not len(parser.idx_root.idx_entries):
        return
    print "*****************INDEX ROOT**************"
    for entry in parser.idx_root.idx_entries:
        print entry.name, entry.file_flags, entry.mft_ref, entry.real_size
    print ''


def print_idx_alloc(parser, clusters = None, show_clusters = False):
    print "*****************INDEX ALLOCATION**************"
    for block in parser.idx_alloc.idx_blocks:
        for entry in block.idx_entries:
            print entry.name, entry.file_flags, entry.mft_ref, entry.real_size
    print ''
    if show_clusters and len(clusters):
        print "Data Clusters: "
        _clusters_ = reduce(lambda x, y: x + y, [range(idx[0], idx[0] + idx[1]) for idx in clusters])
        for idx in range(len(_clusters_[::7])):
            print str(_clusters_[idx * 7:idx * 7 + 7]).replace(",", "")


def print_attr_list(parser):
    print "*****************ATTRIBUTE LIST****************"
    for attr in parser.attr_list.attr_entries:
        print "Type: {0}-{1}\tMFT Entry: {2}\tVCN: {3}".format(attr.attr_type, attr.attr_id, attr.mft_ref, attr.start_vcn)


def print_data(data, clusters, start_vcn, end_vcn, show_clusters = False):
    print "******************DATA INFO******************"
    print "Attribute ID:                    %i" % data.attr_id
    if hasattr(data, 'name') and data.name != None:
        print "Attribute Name:                  %s" % data.name
    else:
        print "Attribute Name:                  N/A"
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
    print "File fragmented:                 %s" % data.fragmented
    if show_clusters and len(clusters):
        print "Data Clusters: "
        _clusters_ = reduce(lambda x, y: x + y, [range(idx[0], idx[0] + idx[1]) for idx in clusters])
        for idx in range(len(_clusters_[::7])):
            print str(_clusters_[idx * 7:idx * 7 + 7]).replace(",", "")
    if data.res_data != None:
        print "Resident Data: %s" % data.res_data
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
    print "$MFT Offset(Bytes): %i" % parser.mft_baseoffset
    print "$MFT Offset(Clusters): %i" % (parser.mft_baseoffset / parser.cluster_size)
    print "$MFTMIR Offset(Bytes): %i" % parser.mft_baseoffset
    print "$MFTMIR Offset(Clusters): %i" % (parser.mft_mir_baseoffset / parser.cluster_size)


def cluster_to_file(parser, cluster):
    for entry in parser.entries:
        if int(cluster) == entry.entry_num:
            print "Cluster: %s, MFT Entry: %s, File: %s" % (cluster, entry.entry_num, entry.name)
            return
        if len(entry.clusters):
            if int(cluster) in reduce(lambda x, y: x + y, [range(idx[0], idx[0] + idx[1]) for idx in entry.clusters]):
                print "Cluster: %s, File: %s, MFT Entry: %s" % (cluster, entry.name, entry.entry_num)
                return
    else:
        print "Cluster: %s unallocated" % cluster

def search(parser, name):
    for entry in parser.entries:
        if entry.name.__contains__(name):
            print "MFT Entry: %d" % entry.entry_num, "Entry Name: %s" % entry.name


if __name__ == "__main__":
    import argparse, sys
    argparser = argparse.ArgumentParser(description = """
    Parses the MFT of an NTFS filesystem. The data returned depends on the flags selected by the user.
    Functionality similar to Sleuthkit's fsstat/istat is possible, as well as a tentative count of various file-types found throughout the system.
    Note: When using this option, the file-type is determined exclusively by extension, so counts may not truly reflect the contents of the system.
    """)
    argparser.add_argument('-t', '--target', help = "Target image/drive to be parsed.", required = True)
    argparser.add_argument('-p', '--partition', type = int, help = "Specify which partition is to be parsed. If none is specified target assumed to be a partition.", default = 0)
    group = argparser.add_mutually_exclusive_group(required = True)
    group.add_argument('-e', '--entry', type = int, help = "Get basic MFT entry data for supplied entry number. Similar to Sleuthkit's istat sans datarun info for ease of viewing. See -d/--data for datarun listings.")
    group.add_argument('-d', '--data', type = int, help = "Get data blocks belonging to file in specified MFT entry.")
    group.add_argument('-f', '--files', type = str, help = "Writes filesystem summary containing basic info (entry num, filename, parent path, mac times, filesize, data clusters and resident data if present) for every file on the filesystem to the specified output filename.")
    group.add_argument('-i', '--info', help = "Get basic volume information. Similar to Sleuthkit's fsstat.", action = 'store_true')
    group.add_argument('-s', '--search', type = str, help = "Find MFT Entry number(s) belonging to files whose names contain the supplied string.")
    group.add_argument('-c', '--cluster', type = int, help = "Map supplied cluster to it's owning file if allocated.")
    args = argparser.parse_args()
    parser = MFTParser(args.target, args.partition)
    parser.setup_mft_data()
    opts = vars(args)

    if opts['entry'] != None or opts['data'] != None:
        try:
            entry_num = int(opts['entry'])
        except:
            entry_num = int(opts['data'])
        parser.parse_mft(start = entry_num, end = entry_num, full_parse = True, cleanup = False, resolve_filepaths = False, parse_index_records = True, get_mactimes = True)
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
        if hasattr(parser, 'attr_list') and parser.attr_list != None:
            print_attr_list(parser)
        if hasattr(parser, 'idx_root') and parser.idx_root != None:
            print_idx_root(parser)
        if hasattr(parser, 'idx_alloc') and parser.idx_alloc != None:
            print_idx_alloc(parser)
        if hasattr(parser, 'filedata') and parser.filedata != None:
            print_data(parser.filedata, [], parser.filedata.start_vcn, parser.filedata.end_vcn)
        if len(parser.data):
            for i in range(len(parser.data)):
                print_data(parser.data[i], [], parser.data[i].start_vcn, parser.data[i].end_vcn)
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
        if hasattr(parser, 'attr_list') and parser.attr_list != None:
            print_attr_list(parser)
        if hasattr(parser, 'idx_root') and parser.idx_root != None:
            print_idx_root(parser)
        if hasattr(parser, 'idx_alloc') and parser.idx_alloc != None:
            print_idx_alloc(parser, parser.idx_alloc.clusters, show_clusters = True)
        if hasattr(parser, 'filedata') and parser.filedata != None:
            res_data = parser.filedata.res_data
            print_data(parser.filedata, parser.filedata.clusters, parser.filedata.start_vcn, parser.filedata.end_vcn, True)
        if len(parser.data):
            for i in range(len(parser.data)):
                res_data = parser.data[i].res_data
                print_data(parser.data[i], parser.data[i].clusters, parser.data[i].start_vcn, parser.data[i].end_vcn, True)
    elif opts['files']:
        parser.parse_mft(full_parse = False, quickstat = False, parse_index_records = False, resolve_filepaths = True, get_mactimes = True)
        get_filesystem_summary(parser, opts['files'])
    elif opts['info']:
        print_fsdata(parser)
    elif opts['search']:
        parser.parse_mft(full_parse = False, quickstat = True, parse_index_records = False, resolve_filepaths = True)
        search(parser, opts['search'])
    elif opts['cluster']:
        parser.parse_mft(full_parse = True, parse_index_records = False, resolve_filepaths = True, quickstat = False)
        cluster_to_file(parser, opts['cluster'])
