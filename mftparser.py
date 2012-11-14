#!/usr/bin/python

from __future__ import division
from mft import *
import os, time, math, gc, sys
from struct import unpack, pack, Struct
from binascii import b2a_hex

MFT_ENTRY_SIZE = 0x400
MFT_HEADER_LEN = 0x38
MFT_ENTRY_SIG = '\x46\x49\x4C\x45'
STANDARD_INFO_SIG = '\x10\x00\x00\x00'
ATTR_LIST_SIG = '\x20\x00\x00\x00'
FILENAME_SIG = '\x30\x00\x00\x00'
OBJECT_ID_SIG = '\x40\x00\x00\x00'
SECURITY_DESC_SIG = '\x50\x00\x00\x00'
VOLUME_NAME_SIG = '\x60\x00\x00\x00'
VOLUME_INFO_SIG = '\x70\x00\x00\x00'
DATA_SIG = '\x80\x00\x00\x00'
INDEX_ROOT_SIG = '\x90\x00\x00\x00'
INDEX_ALLOC_SIG = '\xA0\x00\x00\x00'
BITMAP_SIG = '\xB0\x00\x00\x00'
LOG_UTIL_STREAM_SIG = '\x00\x01\x00\x00' #encryption key
END_OF_ENTRY_SIG = '\xFF\xFF\xFF\xFF'
DATA_RUN_END = '\x00'

UNALLOCATED = 0
ALLOCATED = 1

ATTRIBUTES = {
    'READ_ONLY'             : 0x0001,
    'HIDDEN'                : 0x0002,
    'SYSTEM'                : 0x0004,
    'ARCHIVE'               : 0x0020,
    'DEVICE'                : 0x0040,
    'NORMAL'                : 0x0080,
    'TEMPORARY'             : 0x0100,
    'SPARSE_FILE'           : 0x0200,
    'REPARSE_POINT'         : 0x0400,
    'COMPRESSED'            : 0x0800,
    'OFFLINE'               : 0x1000,
    'NOT_CONTENT_INDEXED'   : 0x2000,
    'ENCRYPTED'             : 0x4000,
    'DIRECTORY'             : 0x10000000,
    'INDEX_VIEW'            : 0x20000000
}

NTFS_EPOCH = 0x19DB1DED53E8000
NTFS_OEM_ID = 0x4E54465320202020
struct_c = Struct("<c")
struct_b = Struct("<B")
struct_h = Struct("<H")
struct_i = Struct("<I")
struct_q = Struct("<Q")

class MFTParser():
    def __init__(self, img = None, partition = 0):
        self.img = open(img, 'rb')
        self.entries = []
        self.mft_data = None
        self.partition_offset = 0
        if partition == 0:
            if unpack(">Q", self.img.read(0xB)[3:])[0] != NTFS_OEM_ID:
                print "Invalid partition specified."
                sys.exit(-1)
        else:
            self.partition_offset = unpack("I", self.img.read(0x1CA + ((partition - 1) * 0x10))[-4:])[0] * 512
            self.img.seek(self.partition_offset)
            if unpack(">Q", self.img.read(0xB)[3:])[0] != NTFS_OEM_ID:
                print "Invalid partition specified."
                sys.exit(-1)
        self.img.seek(self.partition_offset)
        """
        Grab FS data from the MBR
        """
        self.sector_size = struct_h.unpack(self.img.read(0x0D)[-2:])[0]
        self.cluster_size = struct_b.unpack(self.img.read(1))[0] * self.sector_size
        self.num_sectors = unpack('<Q', self.img.read(0x22)[-8:])[0]
        self.num_bytes = self.num_sectors * self.sector_size
        self.num_clusters = int(math.ceil(self.num_bytes / self.cluster_size))
        self.mft_baseoffset = struct_q.unpack(self.img.read(8))[0] * self.cluster_size
        self.mft_mir_baseoffset = struct_q.unpack(self.img.read(8))[0] * self.cluster_size
        self.serial_num = hex(struct_q.unpack(self.img.read(16)[-8:])[0])

    def get_cluster_size(self):
        return self.cluster_size

    def get_num_clusters(self):
        return self.num_clusters

    def setup_mft_data(self):
        """
        The $MFT file (MFT entry 0) stores information about all allocated MFT entries in its data section. This information is used
        to bootstrap the parser. While slightly more complex than just linearly reading each file entry, this method is able to handle
        the case where the MFT is fragmented and or an entry falls on a bad cluster.
        """
        self.entry_offset = self.mft_baseoffset + self.partition_offset
        self.img.seek(self.entry_offset, os.SEEK_SET)
        self.entry = self.img.read(MFT_ENTRY_SIZE)
        fixup_offset = struct_h.unpack(self.entry[4:6])[0] + 2
        fixup_len = struct_h.unpack(self.entry[6:8])[0] + 1
        sec_end = self.sector_size - 2
        # Python strings are immutable...
        self.entry = list(self.entry)
        # For each sector in this entry, replace the fixup values with the original ones.
        for i in range(0, fixup_len, 2):
            self.entry[sec_end] = self.entry[fixup_offset + i]
            self.entry[sec_end + 1] = self.entry[fixup_offset + i + 1]
            sec_end += self.sector_size
        # Pack the list back into binary
        self.entry = pack("<1024c", *self.entry)
        self.entry_offset = self.entry.find(DATA_SIG)
        data_len = struct_i.unpack(self.entry[self.entry_offset + 4:self.entry_offset + 8])[0]
        data = self.entry[self.entry_offset:self.entry_offset + data_len]
        run_off = struct_h.unpack(data[32:34])[0]
        prev_run_offset = 0
        self.mft_data = []
        max_sign = [int(2 ** ((8 * x) - 1) - 1) for x in range(9)]
        file_fragmented = False
        while 1:
            try:
                tmp = b2a_hex(struct_c.unpack(data[run_off])[0])
                run_offset_bytes = int(tmp[0], 16)
                data_run_bytes = int(tmp[1], 16)
                if tmp[0] == '0' or tmp[1] == '0':
                    break
                data = data[run_off + 1:]
                data_run_len = struct_q.unpack(data[0:data_run_bytes] + ('\x00' * (8 - data_run_bytes)))[0]
                data = data[data_run_bytes:]
                run_offset = struct_q.unpack(data[0:run_offset_bytes] + ('\x00' * (8 - run_offset_bytes)))[0]
                data = data[run_offset_bytes:]
                if file_fragmented:
                    if max_sign[run_offset_bytes] >= run_offset:
                        run_offset += prev_run_offset
                    else:
                        run_offset = prev_run_offset - ((max_sign[run_offset_bytes] + 2) -
                                                                (run_offset - max_sign[run_offset_bytes]))
                self.mft_data.extend(range(run_offset, run_offset + data_run_len))
                if data[0] == DATA_RUN_END:
                    break
                else:
                    file_fragmented = True
                    run_off = 0
                    prev_run_offset = run_offset
            except:
                print 'Error occurred while processing $MFT data, incomplete image perhaps? Exiting...'
                return

    def create_SecurityDescriptorTable(self):
        pass

    def parse_mft(self, start = 0, end = None, full_parse = False, quickstat = False, cleanup = True, resolve_filepaths = False, parse_index_records = False, get_mactimes = False):
        """
        The main method/function of the parser. It accepts a 'start' entry if only a single MFT entry's data is desired (in which case the 'end' parameter is set to the same
        value as 'start'). The optional parameters 'full_parse', 'quickstat' and 'cleanup' are used to somewhat fine-tune the parser so that no more parsing/processing occurs
        than necessary. The 'full_parse' option determines whether to completely parse idx root/entries (if entry is a directory) as well as attribute list information (if present)
        of an entry. The 'quickstat' option determines whether to parse the data run information for an entry. The 'cleanup' option determines whether to force the release of file
        entry objects from memory, as Python seems to be a little too lax on its garbage collection mechanisms. This is generally a good idea, as it cuts the memory usage
        of a full-parsing down significantly without adding too much overhead.
        """
        current = start
        self.pos = [0.0, 0.25, 0.50, 0.75]
        self.directories = {}
        self.full_parse = full_parse
        self.quickstat = quickstat
        self.resolve_filepaths = resolve_filepaths
        self.parse_index_records = parse_index_records
        self.cleanup = cleanup
        self.get_mactimes = get_mactimes
        while 1:
            try:
                idx, vcn = math.modf((current * MFT_ENTRY_SIZE) / self.cluster_size)
                idx = self.pos.index(idx)
                if int(vcn) >= len(self.mft_data) or (end != None and current > end):
                    break
                lcn = self.mft_data[int(vcn)]
                address = (lcn * self.cluster_size) + (idx * MFT_ENTRY_SIZE) + self.partition_offset
                self.img.seek(address, os.SEEK_SET)
                self.entry = self.img.read(MFT_ENTRY_SIZE)
                self.entry_offset = 0
                self.data = []
                self.filedata = None
                clusters = []
                self.alloc_status = UNALLOCATED
                self.std_info, self.filename, self.attr_list, res_data = None, None, None, None
                ctime, mtime, atime = None, None, None
                flags = []
                name, parent, real_size, data_size, size = None, None, 0, 0, 0
                if self.entry[0:4] == MFT_ENTRY_SIG:
                    """ Beginning of MFT Entry """
                    self.header = self.parse_mft_header()
                    if self.header.mft_base != 0:
                    # Part of a multi-entry data attribute, not a unique File Entry.
                    # It will eventually be included in an Attribute List attribute
                        current += 1
                        continue
                    while 1:
                        # Trudge through the entry one attribute at a time using their
                        # attribute id's (SIG) and entry lengths to identify attributes.
                        # All entries SHOULD begin with a standard header and end with
                        # the END_OF_ENTRY signature.
                        current_attr_sig = self.entry[self.entry_offset:self.entry_offset + 4]

                        if current_attr_sig == STANDARD_INFO_SIG:
                            self.std_info = self.parse_std_info(self.entry_offset)

                        elif current_attr_sig == ATTR_LIST_SIG:
                            attr_list_len = struct_i.unpack(self.entry[self.entry_offset + 4:self.entry_offset + 8])[0]
                            if self.alloc_status == UNALLOCATED:
                                self.entry_offset += attr_list_len
                            else:
                                self.attr_list = self.parse_attr_list(self.entry_offset)
                                self.parse_attr_list_entries(current)

                        elif current_attr_sig == FILENAME_SIG:
                            filename = self.parse_filename(self.entry_offset)
                            if self.filename != None:
                                if filename.namespace == 2:
                                    continue
                                else:
                                    self.filename = filename
                            else:
                                self.filename = filename

                        elif current_attr_sig == OBJECT_ID_SIG:
                            self.object_id = self.parse_object_id(self.entry_offset)

                        elif current_attr_sig == SECURITY_DESC_SIG:
                            self.sec_desc = self.parse_sec_desc(self.entry_offset)

                        elif current_attr_sig == VOLUME_NAME_SIG:
                            self.volume_name = self.parse_volume_name(self.entry_offset)

                        elif current_attr_sig == VOLUME_INFO_SIG:
                            self.volume_info = self.parse_volume_info(self.entry_offset)

                        elif current_attr_sig == BITMAP_SIG:
                            self.parse_bitmap_attr(self.entry_offset)

                        elif current_attr_sig == DATA_SIG:
                            attr_len = struct_i.unpack(self.entry[self.entry_offset + 4:self.entry_offset + 8])[0]
                            if self.quickstat or self.alloc_status == UNALLOCATED:
                                self.entry_offset += attr_len
                            else:
                                data_attrib = self.parse_data_attr(self.entry_offset)
                                if data_attrib.attr_name == None:
                                    if data_attrib.start_vcn == 0:
                                        self.filedata = data_attrib
                                    else:
                                        self.filedata.clusters.extend(data_attrib.clusters)
                                        self.filedata.end_vcn = max(self.filedata.end_vcn, data_attrib.end_vcn)
                                        if data_attrib.fragmented:
                                            self.filedata.fragmented = True
                                else:
                                    self.data.append(data_attrib)

                        elif current_attr_sig == INDEX_ROOT_SIG:
                            attr_len = struct_i.unpack(self.entry[self.entry_offset + 4:self.entry_offset + 8])[0]
                            if not self.parse_index_records or self.alloc_status == UNALLOCATED:
                                self.entry_offset += attr_len
                            else:
                                self.idx_root = self.parse_idx_root(self.entry_offset)

                        elif current_attr_sig == INDEX_ALLOC_SIG:
                            attr_len = struct_i.unpack(self.entry[self.entry_offset + 4:self.entry_offset + 8])[0]
                            if not self.parse_index_records or self.alloc_status == UNALLOCATED:
                                self.entry_offset += attr_len
                            else:
                                self.idx_alloc = self.parse_idx_alloc(self.entry_offset)

                        elif current_attr_sig == LOG_UTIL_STREAM_SIG:
                            self.parse_data_attr(self.entry_offset)
                            #self.log_util = self.parse_data_attr(self.entry_offset)

                        elif current_attr_sig == END_OF_ENTRY_SIG:
                            break
                        else:
                            # Where the hell are we? Just go to the next entry...
                            break
                    # To Prevent NoneType Errors if a
                    # standard info attribute is not present.
                    if self.get_mactimes:
                        if hasattr(self.std_info, 'ctime'):
                            ctime = self.std_info.ctime
                        if hasattr(self.std_info, 'mtime'):
                            mtime = self.std_info.mtime
                        if hasattr(self.std_info, 'atime'):
                            atime = self.std_info.atime
                    # Likewise for filename attributes
                    if hasattr(self.filename, 'name'):
                        name = self.filename.name
                    if hasattr(self.filename, 'flags'):
                        flags = self.filename.flags
                    if hasattr(self.filename, 'real_size'):
                        real_size = self.filename.real_size
                    if hasattr(self.filename, 'parent'):
                        parent = self.filename.parent
                    # And of course, for data attributes
                    if self.filedata != None:
                        if hasattr(self.filedata, 'clusters') and len(self.filedata.clusters):
                            clusters = self.filedata.clusters
                        if hasattr(self.filedata, 'data_size'):
                            data_size = self.filedata.data_size
                        if hasattr(self.filedata, 'res_data') and self.filedata.res_data != None:
                            res_data = self.filedata.res_data
                    if name != None and 'DIRECTORY' in flags:
                        while parent in self.directories and parent != 5:
                            parent_name, parent = self.directories[parent]
                            name = parent_name + '/' + name
                        self.directories[current] = (name, parent)
                    # We're not interested in MFT specific files nor deleted ones...
                    elif name != None and name[0] != '$' and self.header.flags != 0 and 'DIRECTORY' not in flags:
                        # FILE_RECORDs represent each file's metadata
                        if real_size == 0:
                            size = data_size
                        else:
                            size = real_size
                        self.entries.append(FILE_RECORD(name, current, parent, ctime, mtime, atime, size, clusters, res_data))
                    current += 1
                    if self.cleanup:
                        try:
                            del(clusters)
                            del(self.data)
                            del(self.attr_list)
                        except:
                            pass
                else:
                    # We're not in an MFT Entry, move along now
                    current += 1
            except KeyboardInterrupt:
                print "User aborted"
                break
        """
        if self.resolve_filepaths:
            for entry in self.entries:
                parent = entry.parent
                entry.name = self.directories[parent][0] + '/' + entry.name
        """
        del(self.directories)
        gc.collect()
        self.img.close()
        return self.entries


    def parse_mft_header(self):
        """ Parse the Standard MFT Entry header. All entries should begin with this header. SHOULD.. """
        # First things first, we need to deal with the fixup values. Grab the saved values from the fixup
        # array and place them where they belong, namely the last 2 bytes of each sector.
        fixup_offset = struct_h.unpack(self.entry[4:6])[0] + 2
        fixup_len = struct_h.unpack(self.entry[6:8])[0] + 1
        sec_end = self.sector_size - 2
        # Python strings are immutable...
        self.entry = list(self.entry)
        # For each sector in this entry, replace the fixup values with the original ones.
        for i in range(0, fixup_len, 2):
            self.entry[sec_end] = self.entry[fixup_offset + i]
            self.entry[sec_end + 1] = self.entry[fixup_offset + i + 1]
            sec_end += self.sector_size
        # Pack the list back into binary
        self.entry = pack("<1024c", *self.entry)
        lsn = struct_q.unpack(self.entry[8:16])[0]
        seq_num = struct_h.unpack(self.entry[16:18])[0]
        # Number of references to file
        lnk_cnt = struct_h.unpack(self.entry[18:20])[0]
        # Should always be 56 (0x38) bytes from start of header
        # first_attr_off = struct_h.unpack(self.entry[20:22])[0]
        # Directory, System, Hidden, etc.
        flags = struct_h.unpack(self.entry[22:24])[0]
        self.alloc_status = flags & 0x1
        # If mft_base != 0, then we're in an extended data attribute entry
        # owned by mft_base's entry. Its attributes could not fit in a single record
        # so another entry was reserved for it.
        mft_base = struct_q.unpack(self.entry[32:40])[0] & 0xFFFFFFFFFFFF
        # next_attr_id = struct_h.unpack(self.entry[40:42])[0]
        # MFT entry number, similar to an inode number
        entry_num = struct_i.unpack(self.entry[44:48])[0]
        self.entry_offset += MFT_HEADER_LEN
        # Return an object modeling the entry's standard header
        return MFT_STANDARD_HEADER(lsn, seq_num, lnk_cnt, flags, entry_num, mft_base)

    def parse_attr_list(self, offset):
        """Parse the Attribute List attribute of an entry. Entries only have an attribute list if a single entry is too small
           to hold all the metadata of the entry's attributes."""
        attr_list_len = struct_i.unpack(self.entry[offset + 4:offset + 8])[0]
        non_resident = struct_b.unpack(self.entry[offset + 8])[0]
        if non_resident == 0:
            attr_id = struct_h.unpack(self.entry[offset + 14:offset + 16])[0]
            attr_list = self.entry[offset + 24:offset + 24 + attr_list_len]
            offset = 0
            attr_entries = []
            while offset < attr_list_len - 24:
                attr_type = struct_i.unpack(attr_list[offset:offset + 4])[0]
                if attr_type == 0:
                    break
                attr_len = struct_h.unpack(attr_list[offset + 4:offset + 6])[0]
                name_length = struct_b.unpack(attr_list[offset + 6])[0]
                name_offset = struct_b.unpack(attr_list[offset + 7])[0]
                start_vcn = struct_q.unpack(attr_list[offset + 8:offset + 16])[0] & 0xFFFFFFFFFFFF
                mft_ref = struct_q.unpack(attr_list[offset + 16:offset + 24])[0] & 0xFFFFFFFFFFFF
                attr_id = struct_b.unpack(attr_list[offset + 24])[0]
                name = attr_list[offset + name_offset: offset + name_offset + (2 * name_length)].replace('\x00', '')
                attr_entries.append(ATTR_LIST_ENTRY(attr_type, attr_len, name_length, start_vcn, mft_ref, attr_id, name))
                offset += attr_len
            self.entry_offset += attr_list_len
            return ATTR_LIST(non_resident, attr_list_len, attr_list_len, attr_entries, None)
        else:
            prev_img_offset = self.img.tell()
            attr_id = struct_h.unpack(self.entry[offset + 14:offset + 16])[0]
            start_vcn = struct_q.unpack(self.entry[offset + 16:offset + 24])[0]
            #end_vcn = struct_q.unpack(self.entry[offset + 24:offset + 32])[0]
            data_run_off = struct_h.unpack(self.entry[offset + 32:offset + 34])[0]
            #alloc_size = struct_q.unpack(self.entry[offset + 40:offset + 48])[0]
            real_size = struct_q.unpack(self.entry[offset + 48:offset + 56])[0] & 0xFFFFFFFFFFFF
            init_size = struct_q.unpack(self.entry[offset + 56:offset + 64])[0] & 0xFFFFFFFFFFFF
            data_run_len = struct_q.unpack(self.entry[offset + 40:offset + 48])[0] & 0xFFFFFFFFFFFF
            data = self.entry[offset + data_run_off:offset + data_run_off + real_size]
            run_offset = 0
            prev_run_offset = 0
            max_sign = [int(2 ** ((8 * x) - 1) - 1) for x in range(9)]
            file_fragmented = False
            attr_entries = []
            clusters = []
            while 1:
                tmp = b2a_hex(struct_c.unpack(data[0])[0])
                run_offset_bytes = int(tmp[0], 16)
                data_run_bytes = int(tmp[1], 16)
                if tmp[0] == '0' or tmp[1] == '0':
                    break
                data = data[run_offset + 1:]
                data_run_len = struct_q.unpack(data[0:data_run_bytes % 8] + ('\x00' * (8 - (data_run_bytes % 8))))[0] & 0xFFFFFFFFFFFF
                data = data[data_run_bytes:]
                run_offset = struct_q.unpack(data[0:run_offset_bytes] + ('\x00' * (8 - run_offset_bytes)))[0] & 0xFFFFFFFFFFFF
                data = data[run_offset_bytes:]
                if file_fragmented:
                        if max_sign[run_offset_bytes] >= run_offset:
                            run_offset += prev_run_offset
                        else:
                            run_offset = prev_run_offset - ((max_sign[run_offset_bytes] + 2) -
                                                                   (run_offset - max_sign[run_offset_bytes]))
                for i in range(data_run_len):
                    lcn = (run_offset + i + start_vcn)
                    self.img.seek((lcn * self.cluster_size) + self.partition_offset, os.SEEK_SET)
                    attr_entry = self.img.read(self.cluster_size)
                    offset = 0
                    while 1:
                        try:
                            attr_type = struct_i.unpack(attr_entry[offset:offset + 4])[0]
                            if attr_type == 0:
                                break
                        except:
                            break
                        attr_len = struct_h.unpack(attr_entry[offset + 4:offset + 6])[0]
                        name_length = struct_b.unpack(attr_entry[offset + 6])[0]
                        name_offset = struct_b.unpack(attr_entry[offset + 7])[0]
                        entry_start_vcn = struct_q.unpack(attr_entry[offset + 8:offset + 16])[0] & 0xFFFFFFFFFFFF
                        mft_ref = struct_q.unpack(attr_entry[offset + 16:offset + 24])[0] & 0xFFFFFFFFFFFF
                        attr_id = struct_b.unpack(attr_entry[offset + 24])[0]
                        attr_name = attr_entry[offset + name_offset: offset + name_offset + (2 * name_length)].replace('\x00', '')
                        attr_entries.append(ATTR_LIST_ENTRY(attr_type, attr_len, name_length, entry_start_vcn, mft_ref, attr_id, attr_name))
                        offset += attr_len
                clusters.append((run_offset, data_run_len))
                if data[0] == DATA_RUN_END:
                    break
                else:
                    file_fragmented = True
                    prev_run_offset = run_offset
                    continue
            self.entry_offset += attr_list_len
            self.img.seek(prev_img_offset, os.SEEK_SET)
            return ATTR_LIST(non_resident, real_size, init_size, attr_entries, clusters)

    def parse_attr_list_entries(self, current):
        orig_entry_offset = self.entry_offset
        orig_entry = self.entry
        orig_img_offset = self.img.tell()
        for attr in self.attr_list.attr_entries:
            if attr.mft_ref != current:
                idx, vcn = math.modf((attr.mft_ref * MFT_ENTRY_SIZE) / self.cluster_size)
                idx = self.pos.index(idx)
                lcn = self.mft_data[int(vcn)]
                address = (lcn * self.cluster_size) + (idx * MFT_ENTRY_SIZE) + self.partition_offset
                self.img.seek(address, os.SEEK_SET)
                self.entry = self.img.read(MFT_ENTRY_SIZE)
                self.parse_mft_header()
                self.entry_offset = MFT_HEADER_LEN
                if self.entry[self.entry_offset:self.entry_offset + 4] == FILENAME_SIG:
                    filename = self.parse_filename(self.entry_offset)
                    if self.filename != None:
                        if filename.namespace == 2:
                            continue
                        else:
                            self.filename = filename
                    else:
                        self.filename = filename
                elif self.entry[self.entry_offset:self.entry_offset + 4] == INDEX_ROOT_SIG:
                    attr_len = struct_i.unpack(self.entry[self.entry_offset + 4:self.entry_offset + 8])[0]
                    self.entry_offset += attr_len
                elif self.entry[self.entry_offset:self.entry_offset + 4] == DATA_SIG:
                    data_attrib = self.parse_data_attr(self.entry_offset)
                    if data_attrib.attr_name == None:
                        if data_attrib.start_vcn == 0:
                            self.filedata = data_attrib
                        else:
                            self.filedata.clusters.extend(data_attrib.clusters)
                            self.filedata.end_vcn = max(self.filedata.end_vcn, data_attrib.end_vcn)
                            if data_attrib.fragmented:
                                self.filedata.fragmented = True
                    else:
                        self.data.append(data_attrib)
                self.img.seek(orig_img_offset, os.SEEK_SET)
                self.entry_offset = orig_entry_offset
                self.entry = orig_entry
            else:
                offset = self.entry_offset
                if self.entry[offset:offset + 4] == DATA_SIG:
                    data_attrib = self.parse_data_attr(self.entry_offset)
                    if data_attrib.attr_name == None:
                        if data_attrib.start_vcn == 0:
                            self.filedata = data_attrib
                        else:
                            self.filedata.clusters.extend(data_attrib.clusters)
                            self.filedata.end_vcn = max(self.filedata.end_vcn, data_attrib.end_vcn)
                            if data_attrib.fragmented:
                                self.filedata.fragmented = True
                    else:
                        self.data.append(data_attrib)
        return

    #def parse_attr_def(self, offset):
        #offset += 4
        #attr_name = self.entry[offset:offset+128]
        #type_id = struct_i.unpack(self.entry[offset+128:offset+132])[0]
        #display_rule = struct_i.unpack(self.entry[offset+132:offset+136])[0]
        #collation_rule = struct_i.unpack(self.entry[offset+136:offset+140])[0]
        #flags = struct_i.unpack(self.entry[offset+140:offset+144])[0]
        #min_size = struct_q.unpack(self.entry[offset+144:offset+152])[0]
        #max_size = struct_q.unpack(self.entry[offset+152:offset+160])[0]


    def parse_std_info(self, offset):
        attr_len = struct_i.unpack(self.entry[offset + 4:offset + 8])[0]
        std_info = self.entry[offset + 24:offset + attr_len]
        ctime, mtime, atime, sid = None, None, None, None
        if self.get_mactimes:
            try:
                ctime = time.ctime((struct_q.unpack(std_info[0:8])[0] - NTFS_EPOCH) / 10 ** (7))
                mtime = time.ctime((struct_q.unpack(std_info[8:16])[0] - NTFS_EPOCH) / 10 ** (7))
                #mft_mod_time = time.ctime((struct_q.unpack(std_info[16:24])[0] - NTFS_EPOCH) / 10**(7))
                atime = time.ctime((struct_q.unpack(std_info[24:32])[0] - NTFS_EPOCH) / 10 ** (7))
            except:
                pass
        flags = [key for key in ATTRIBUTES if struct_i.unpack(std_info[32:36])[0] & ATTRIBUTES[key]]
        try:
            sid = struct_i.unpack(std_info[52:56])[0]
        except:
            pass
        self.entry_offset += attr_len
        return STANDARD_INFO(ctime, mtime, atime, flags, sid)

    def parse_filename(self, offset):
        attr_len = struct_i.unpack(self.entry[offset + 4:offset + 8])[0]
        filename = self.entry[offset + 24:offset + attr_len]
        parent = struct_q.unpack(filename[0:8])[0] & 0xFFFFFFFFFFFF
        ctime, mtime, atime = None, None, None
        if self.get_mactimes:
            try:
                ctime = time.ctime((struct_q.unpack(filename[8:16])[0] - NTFS_EPOCH) / 10 ** (7))
                mtime = time.ctime((struct_q.unpack(filename[16:24])[0] - NTFS_EPOCH) / 10 ** (7))
                #mft_mod_time = time.ctime((struct_q.unpack(filename[24:32])[0] - NTFS_EPOCH) / 10**(7))
                atime = time.ctime((struct_q.unpack(filename[32:40])[0] - NTFS_EPOCH) / 10 ** (7))
            except:
                pass
        alloc_size = struct_q.unpack(filename[40:48])[0] & 0xFFFFFFFFFFFF
        real_size = struct_q.unpack(filename[48:56])[0] & 0xFFFFFFFFFFFF
        flags = [key for key in ATTRIBUTES if struct_i.unpack(filename[56:60])[0] & ATTRIBUTES[key]]
        name_length = struct_b.unpack(filename[64])[0]
        namespace = struct_b.unpack(filename[65])[0]
        name = filename[66: 66 + (2 * name_length)].replace('\x00', '')
        self.entry_offset += attr_len
        return FILENAME(parent, ctime, mtime, atime, alloc_size, real_size, flags, name, namespace)

    def parse_object_id(self, offset):
        object_id = b2a_hex(self.entry[offset + 39:offset + 23:-1])
        object_id = '-'.join([object_id[0:8], object_id[8:12], object_id[12:16], object_id[16:20], object_id[20:]])
        self.entry_offset += 40
        return OBJECT_ID(object_id)

    def parse_volume_name(self, offset):
        self.entry_offset += struct_i.unpack(self.entry[offset + 4:offset + 8])[0]
        return None

    def parse_volume_info(self, offset):
        self.entry_offset += struct_i.unpack(self.entry[offset + 4:offset + 8])[0]
        return None

    def parse_idx_root(self, offset):
        attr_len = struct_i.unpack(self.entry[offset + 4:offset + 8])[0]
        idx_root = self.entry[offset:offset + attr_len]
        #attr_type = idx_root[0:4]
        name_length = struct_b.unpack(idx_root[9])[0]
        name_offset = struct_h.unpack(idx_root[10:12])[0]
        attr_name = idx_root[name_offset:name_offset + (2 * name_length)].replace('\x00', '')
        attr_flags = struct_h.unpack(idx_root[12:14])[0]
        attr_id = struct_h.unpack(idx_root[14:16])[0]
        #attr_data_size = struct_i.unpack(idx_root[16:20])[0]
        attr_data_offset = struct_h.unpack(idx_root[20:22])[0]
        idx_root = idx_root[attr_data_offset:]
        #coll_sort_rule = struct_i.unpack(idx_root[4:8])[0]
        #clusters_per_entry = int(b2a_hex(struct_c.unpack( idx_root[12])[0]), 16)
        first_idx_offset = struct_i.unpack(idx_root[16:20])[0]
        index_size = struct_i.unpack(idx_root[20:24])[0]
        #index_alloc_size = struct_i.unpack(idx_root[24:28])[0]
        header_flags = struct_i.unpack(idx_root[28:32])[0]
        if attr_name == "$SDH" or attr_name == "$SII":
            self.entry_offset += attr_len
            return INDEX_ROOT(attr_name, attr_flags, attr_id, index_size, header_flags, [])
        idx_entries = []
        idx_buffer = idx_root[first_idx_offset + 16:]
        offset = 0
        while 1:
            flags = struct_i.unpack(idx_buffer[offset + 12:offset + 16])[0] & 0xFFFF
            if flags & 0x2:
                break
            mft_ref = struct_q.unpack(idx_buffer[offset:offset + 8])[0] & 0xFFFFFFFFFFFF
            entry_len = struct_h.unpack(idx_buffer[offset + 8:offset + 10])[0]
            #key_len = struct_h.unpack(idx_buffer[offset + 10:offset + 12])[0]
            parent = struct_q.unpack(idx_buffer[offset + 16:offset + 24])[0] & 0xFFFFFFFFFFFF
            entry_ctime, entry_mtime, entry_atime = None, None, None
            if self.get_mactimes:
                try:
                    entry_ctime = time.ctime((struct_q.unpack(idx_buffer[offset + 24:offset + 32])[0] - NTFS_EPOCH) / 10 ** (7))
                    entry_mtime = time.ctime((struct_q.unpack(idx_buffer[offset + 32:offset + 40])[0] - NTFS_EPOCH) / 10 ** (7))
                    #entry_mft_mod_time = time.ctime((struct_q.unpack(idx_buffer[40:48])[0] - NTFS_EPOCH) / 10**(7))
                    entry_atime = time.ctime((struct_q.unpack(idx_buffer[offset + 48:offset + 56])[0] - NTFS_EPOCH) / 10 ** (7))
                except:
                    pass
            entry_alloc_size = struct_q.unpack(idx_buffer[offset + 56:offset + 64])[0] & 0xFFFFFFFFFFFF
            entry_real_size = struct_q.unpack(idx_buffer[offset + 64:offset + 72])[0] & 0xFFFFFFFFFFFF
            entry_flags = [key for key in ATTRIBUTES if struct_i.unpack(idx_buffer[offset + 72:offset + 76])[0] & ATTRIBUTES[key]]
            entry_name_length = struct_b.unpack(idx_buffer[offset + 80])[0]
            entry_namespace = struct_b.unpack(idx_buffer[offset + 81])[0]
            if entry_namespace == 2:
                offset += entry_len
                continue
            entry_filename = idx_buffer[offset + 82:offset + 82 + (2 * entry_name_length)].replace('\x00', '')
            idx_entries.append(INDEX_ENTRY(mft_ref, flags, parent, entry_ctime, entry_mtime, entry_atime, entry_alloc_size, entry_real_size,  entry_flags, entry_filename))
            offset += entry_len
        self.entry_offset += attr_len
        return INDEX_ROOT(attr_name, attr_flags, attr_id, index_size, header_flags, idx_entries)

    def parse_idx_alloc(self, offset):
        orig_img_offset = self.img.tell()
        attr_len = struct_i.unpack(self.entry[offset + 4:offset + 8])[0]
        idx_alloc = self.entry[offset:offset + attr_len]
        name_length = struct_b.unpack(idx_alloc[9])[0]
        name_offset = struct_h.unpack(idx_alloc[10:12])[0]
        attr_flags = struct_h.unpack(idx_alloc[12:14])[0]
        attr_id = struct_h.unpack(idx_alloc[14:16])[0]
        start_vcn = struct_q.unpack(idx_alloc[16:24])[0] & 0xFFFFFFFFFFFF
        end_vcn = struct_q.unpack(idx_alloc[24:32])[0] & 0xFFFFFFFFFFFF
        run_off = struct_h.unpack(idx_alloc[32:34])[0]
        alloc_init_size = struct_q.unpack(idx_alloc[40:48])[0] & 0xFFFFFFFFFFFF
        attr_name = idx_alloc[name_offset:name_offset + (2 * name_length)].replace('\x00', '')
        if attr_name == "$SDH" or attr_name == "$SII":
            self.entry_offset += attr_len
            return INDEX_ALLOC(attr_name, attr_flags, attr_id, start_vcn, end_vcn, 0, [], None)
        data = idx_alloc[run_off:run_off + alloc_init_size]
        idx_blocks = []
        prev_run_offset = 0
        max_sign = [int(2 ** ((8 * x) - 1) - 1) for x in range(9)]
        fragmented = False
        run_off = 0
        clusters = []
        while 1:
            tmp = b2a_hex(struct_c.unpack(data[run_off])[0])
            run_offset_bytes = int(tmp[0], 16)
            run_bytes = int(tmp[1], 16)
            if tmp[0] == '0' or tmp[1] == '0':
                break
            data = data[run_off + 1:]
            run_len = struct_q.unpack(data[:run_bytes % 8] + ('\x00' * (8 - (run_bytes % 8))))[0] & 0xFFFFFFFFFFFF
            data = data[run_bytes:]
            run_offset = struct_q.unpack(data[:run_offset_bytes] + ('\x00' * (8 - run_offset_bytes)))[0] & 0xFFFFFFFFFFFF
            data = data[run_offset_bytes:]
            if fragmented:
                    if max_sign[run_offset_bytes] >= run_offset:
                        run_offset += prev_run_offset
                    else:
                        run_offset = prev_run_offset - ((max_sign[run_offset_bytes] + 2) -
                                                               (run_offset - max_sign[run_offset_bytes]))
            clusters.append((run_offset, run_len))
            for i in range(run_len):
                idx_blocks.append(self.parse_index_block((run_offset + i + start_vcn)))
            if data[0] == DATA_RUN_END:
                break
            else:
                run_off = 0
                fragmented = True
                prev_run_offset = run_offset
                continue
        self.entry_offset += attr_len
        self.img.seek(orig_img_offset)
        return INDEX_ALLOC(attr_name, attr_flags, attr_id, start_vcn, end_vcn, run_len, idx_blocks, clusters)

    def parse_index_block(self, lcn):
        self.img.seek((lcn * self.cluster_size) + self.partition_offset, os.SEEK_SET)
        index_block = self.img.read(self.cluster_size)
        fixup_offset = struct_h.unpack(index_block[4:6])[0] + 2
        fixup_len = struct_h.unpack(index_block[6:8])[0] + 1
        log_seq = struct_q.unpack(index_block[8:16])[0]
        index_block_vcn = struct_q.unpack(index_block[16:24])[0] & 0xFFFFFFFF
        sec_end = self.sector_size - 2
        index_block = list(index_block)
        for i in range(0, fixup_len, 2):
            index_block[sec_end:sec_end + 1] = index_block[fixup_offset + i:fixup_offset + i + 1]
            sec_end += self.sector_size
        index_block = pack("<%dc" % len(index_block), *index_block)
        first_idx_offset = struct_i.unpack(index_block[24:28])[0] + 24
        index_size = struct_i.unpack(index_block[28:32])[0] + 24
        #alloc_size = struct_i.unpack(index_block[32:36])[0] + 24
        header_flags = struct_i.unpack(index_block[36:40])[0]
        idx_entries = []
        index_buffer = index_block[first_idx_offset:]
        offset = 0
        while 1:
            flags = struct_i.unpack(index_buffer[offset + 12:offset + 16])[0] & 0xFFFF
            if flags & 0x2:
                break
            mft_ref = struct_q.unpack(index_buffer[offset:offset + 8])[0] & 0xFFFFFFFFFFFF
            if mft_ref == 0:
                break
            entry_len = struct_h.unpack(index_buffer[offset + 8:offset + 10])[0]
            #key_len = struct_h.unpack(index_buffer[offset + 10:offset + 12])[0]
            flags = struct_i.unpack(index_buffer[offset + 12:offset + 16])[0] & 0xFFFF
            parent = struct_q.unpack(index_buffer[offset + 16:offset + 24])[0] & 0xFFFFFFFFFFFF
            entry_ctime, entry_mtime, entry_atime = None, None, None
            """
            if self.get_mactimes:
                try:
                    entry_ctime = time.ctime((struct_q.unpack(index_buffer[offset + 24:offset + 32])[0] - NTFS_EPOCH) / 10 ** (7))
                    entry_mtime = time.ctime((struct_q.unpack(index_buffer[offset + 40:offset + 48])[0] - NTFS_EPOCH) / 10 ** (7))
                    entry_atime = time.ctime((struct_q.unpack(index_buffer[offset + 48:offset + 56])[0] - NTFS_EPOCH) / 10 ** (7))
                except:
                    pass
            """
            entry_alloc_size = struct_q.unpack(index_buffer[offset + 56:offset + 64])[0] & 0xFFFFFFFFFFFF
            entry_real_size = struct_q.unpack(index_buffer[offset + 64:offset + 72])[0] & 0xFFFFFFFFFFFF
            entry_flags = [key for key in ATTRIBUTES if struct_i.unpack(index_buffer[offset + 72:offset + 76])[0] & ATTRIBUTES[key]]
            entry_name_length = struct_b.unpack(index_buffer[offset + 80])[0]
            entry_namespace = struct_b.unpack(index_buffer[offset + 81])[0]
            if entry_namespace == 2:
                offset += entry_len
                continue
            entry_filename = index_buffer[offset + 82:offset + 82 + (2 * entry_name_length)].replace('\x00', '')
            idx_entries.append(INDEX_ENTRY(mft_ref, flags, parent, entry_ctime, entry_mtime, entry_atime, entry_alloc_size, entry_real_size, entry_flags, entry_filename))
            offset += entry_len
        return INDEX_BLOCK(log_seq, index_block_vcn, index_size, None, header_flags, idx_entries)

    def parse_data_attr(self, offset):
        clusters = []
        attr_name, res_data, start_vcn, end_vcn = None, None, 0, 0
        fragmented = False
        prev_run_offset = 0
        max_sign = [int(2 ** ((8 * x) - 1) - 1) for x in range(9)]
        attr_len = struct_i.unpack(self.entry[offset + 4:offset + 8])[0]
        data = self.entry[offset:offset + attr_len]
        nonresident = int(b2a_hex(struct_c.unpack(data[8])[0]), 16)
        name_length = struct_b.unpack(data[9])[0]
        name_offset = struct_h.unpack(data[10:12])[0]
        if name_length != 0:
            attr_name = data[name_offset:name_offset + (2 * name_length)].replace('\x00', '')
        flags = [key for key in ATTRIBUTES if struct_h.unpack(data[12:14])[0] & ATTRIBUTES[key]]
        attr_id = struct_h.unpack(data[14:16])[0]
        if nonresident:
            start_vcn = struct_q.unpack(data[16:24])[0]
            end_vcn = struct_q.unpack(data[24:32])[0]
            run_off = struct_h.unpack(data[32:34])[0]
            alloc_size = struct_q.unpack(data[40:48])[0]
            real_size = struct_q.unpack(data[48:56])[0]
            while 1:
                tmp = b2a_hex(struct_c.unpack(data[run_off])[0])
                run_offset_bytes = int(tmp[0], 16)
                data_run_bytes = int(tmp[1], 16)
                if tmp[0] == '0' or tmp[1] == '0':
                    break
                data = data[run_off + 1:]
                data_run_len = struct_q.unpack(data[0:data_run_bytes % 8] + ('\x00' * (8 - (data_run_bytes % 8))))[0] & 0xFFFFFFFFFFFF
                data = data[data_run_bytes:]
                run_offset = struct_q.unpack(data[0:run_offset_bytes] + ('\x00' * (8 - run_offset_bytes)))[0] & 0xFFFFFFFFFFFF
                data = data[run_offset_bytes:]
                if fragmented:
                    if max_sign[run_offset_bytes] >= run_offset:
                        run_offset += prev_run_offset
                    else:
                        run_offset = prev_run_offset - ((max_sign[run_offset_bytes] + 2) -
                                                               (run_offset - max_sign[run_offset_bytes]))
                clusters.append((run_offset, data_run_len))
                if data[0] == DATA_RUN_END:
                    break
                else:
                    fragmented = True
                    run_off = 0
                    prev_run_offset = run_offset
                    continue
        else:
            real_size = struct_i.unpack(data[12:16])[0]
            alloc_size = struct_i.unpack(data[16:20])[0]
            content_off = struct_h.unpack(data[20:22])[0]
            res_data = data[content_off:]
        self.entry_offset += attr_len
        return DATA_ATTR(nonresident, flags, attr_id, start_vcn, end_vcn, alloc_size, real_size, clusters, fragmented, res_data, attr_name)

    def parse_bitmap_attr(self, offset):
        self.entry_offset += struct_i.unpack(self.entry[offset + 4:offset + 8])[0]
        return None

    def parse_sec_desc(self, offset):
        self.entry_offset += struct_i.unpack(self.entry[offset + 4:offset + 8])[0]
        return None

    def main(self):
        self.setup_mft_data()
        return self.parse_mft()
