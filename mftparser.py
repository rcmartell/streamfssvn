#!/usr/bin/python

from __future__ import division
from mft import *
import os, time, math, gc
from struct import unpack, pack
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

class MFTParser():
    def __init__(self, img = None):
        self.img = open(img, 'rb')
        self.entries = []
        self.mft_data = None
        self.partoffset = None
        # Is the target a partition or an entire disk
        if unpack(">Q", self.img.read(0xB)[3:])[0] == NTFS_OEM_ID:
            # Partition
            self.partoffset = 0
        else:
            # Raw Disk:
            # Read starting sector for first partition from MBR
            self.partoffset = unpack("I", self.img.read(0x1BF)[-4:])[0] * 512
        self.img.seek(self.partoffset)
        """
        Grab FS data from the MBR
        """
        self.sector_size = unpack('<H', self.img.read(0x0D)[-2:])[0]
        self.cluster_size = unpack("<B", self.img.read(1))[0] * self.sector_size
        self.num_sectors = unpack('<Q', self.img.read(0x22)[-8:])[0]
        self.num_bytes = self.num_sectors * self.sector_size
        self.num_clusters = int(math.ceil(self.num_bytes / self.cluster_size))
        self.mft_baseoffset = unpack("<Q", self.img.read(8))[0] * self.cluster_size
        self.mft_mir_baseoffset = unpack("<Q", self.img.read(8))[0] * self.cluster_size
        self.serial_num = hex(unpack("<Q", self.img.read(16)[-8:])[0])

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
        self.offset = self.mft_baseoffset + self.partoffset
        self.img.seek(self.offset, os.SEEK_SET)
        self.entry = self.img.read(MFT_ENTRY_SIZE)
        fix_arr_off = unpack("<H", self.entry[4:6])[0] + 2
        fix_arr_len = unpack("<H", self.entry[6:8])[0] + 1
        sec_end = self.sector_size - 2
        # Python strings are immutable...
        self.entry = list(self.entry)
        # For each sector in this entry, replace the fixup values with the original ones.
        for i in range(0, fix_arr_len, 2):
            self.entry[sec_end] = self.entry[fix_arr_off + i]
            self.entry[sec_end + 1] = self.entry[fix_arr_off + i + 1]
            sec_end += self.sector_size
        # Pack the list back into binary
        self.entry = pack("<1024c", *self.entry)
        self.offset = self.entry.find(DATA_SIG)
        data_len = unpack("<I", self.entry[self.offset + 4:self.offset + 8])[0]
        data = self.entry[self.offset:self.offset + data_len]
        run_off = unpack("<H", data[32:34])[0]
        prev_data_runoffset = 0
        self.mft_data = []
        max_sign = [int(2 ** ((8 * x) - 1) - 1) for x in range(9)]
        file_fragmented = False
        while True:
            try:
                tmp = b2a_hex(unpack("<c", data[run_off])[0])
                data_runoffset_bytes = int(tmp[0], 16)
                data_run_bytes = int(tmp[1], 16)
                if tmp[0] == '0' or tmp[1] == '0':
                    break
                data = data[run_off + 1:]
                data_run_len = unpack("<Q", data[0:data_run_bytes] + ('\x00' * (8 - data_run_bytes)))[0]
                data = data[data_run_bytes:]
                data_runoffset = unpack("<Q", data[0:data_runoffset_bytes] + ('\x00' * (8 - data_runoffset_bytes)))[0]
                data = data[data_runoffset_bytes:]
                if file_fragmented:
                    if max_sign[data_runoffset_bytes] >= data_runoffset:
                        data_runoffset += prev_data_runoffset
                    else:
                        data_runoffset = prev_data_runoffset - ((max_sign[data_runoffset_bytes] + 2) -
                                                                (data_runoffset - max_sign[data_runoffset_bytes]))
                self.mft_data.extend(range(data_runoffset, data_runoffset + data_run_len))
                if data[0] == DATA_RUN_END:
                    break
                else:
                    file_fragmented = True
                    run_off = 0
                    prev_data_runoffset = data_runoffset
            except:
                print 'Error occurred while processing $MFT data, incomplete image perhaps? Exiting...'
                return

    def create_SecurityDescriptorTable(self):
        pass

    def parse_mft(self, start = 0, end = None, fullParse = False, quickstat = False, cleanup = True, getFullPaths = True, getIDXEntries = False):
        """
        The main method/function of the parser. It accepts a 'start' entry if only a single MFT entry's data is desired (in which case the 'end' parameter is set to the same
        value as 'start'). The optional parameters 'fullParse', 'quickstat' and 'cleanup' are used to somewhat fine-tune the parser so that no more parsing/processing occurs
        than necessary. The 'fullParse' option determines whether to completely parse idx root/entry information (if present) of an entry. The 'quickstat' option determines
        whether to parse the data run information for an entry. The 'cleanup' option determines whether to force the release of file entry objects from memory, as Python
        seems to be a little too lax on its garbage collection mechanisms. This is generally a good idea, as it cuts the memory usage of a full-parsing down significantly
        without adding too much overhead.
        """
        count = start
        inode = start
        self.pos = [0.0, 0.25, 0.50, 0.75]
        self.directories = {}
        self.fullParse = fullParse
        self.quickstat = quickstat
        self.getFullPaths = getFullPaths
        self.getIDXEntries = getIDXEntries
        self.cleanup = cleanup
        while True:
            try:
                idx, vcn = math.modf((count * MFT_ENTRY_SIZE) / self.cluster_size)
                idx = self.pos.index(idx)
                if int(vcn) >= len(self.mft_data) or (end != None and inode > end):
                    break
                lcn = self.mft_data[int(vcn)]
                address = (lcn * self.cluster_size) + (idx * MFT_ENTRY_SIZE) + self.partoffset
                self.img.seek(address, os.SEEK_SET)
                self.entry = self.img.read(MFT_ENTRY_SIZE)
                self.offset = 0
                self.data = []
                clusters = []
                self.entry_num = 0
                self.std_info, self.filename, self.attr_list, res_data = None, None, None, None
                # ctime, mtime, atime = None, None, None
                flags = []
                name, parent, real_size, data_size, size = None, None, 0, 0, 0
                if self.entry[0:4] == MFT_ENTRY_SIG:
                    """ Beginning of MFT Entry """
                    self.header = self.parse_header()
                    if self.header.mft_base != 0:
                    # Part of a multi-entry data attribute, not a unique File Entry.
                    # It will eventually be included in an Attribute List attribute
                        count += 1
                        inode += 1
                        continue
                    while True:
                        # Trudge through the entry one attribute at a time using their
                        # attribute id's (SIG) and entry lengths to identify attributes.
                        # All entries SHOULD begin with a standard header and end with
                        # the END_OF_ENTRY signature.
                        if self.entry[self.offset:self.offset + 4] == STANDARD_INFO_SIG:
                            self.std_info = self.parse_std_info(self.offset)

                        elif self.entry[self.offset:self.offset + 4] == ATTR_LIST_SIG:
                            self.attr_list = self.parse_attr_list(self.offset)
                            self.parse_attr_list_entries(count)

                        elif self.entry[self.offset:self.offset + 4] == FILENAME_SIG:
                            filename = self.parse_filename(self.offset)
                            if self.filename != None:
                                if filename.namespace == 2:
                                    continue
                                else:
                                    self.filename = filename
                            else:
                                self.filename = filename

                        elif self.entry[self.offset:self.offset + 4] == OBJECT_ID_SIG:
                            self.object_id = self.parse_object_id(self.offset)

                        elif self.entry[self.offset:self.offset + 4] == SECURITY_DESC_SIG:
                            self.sec_desc = self.parse_sec_desc(self.offset)

                        elif self.entry[self.offset:self.offset + 4] == VOLUME_NAME_SIG:
                            self.volume_name = self.parse_volume_name(self.offset)

                        elif self.entry[self.offset:self.offset + 4] == VOLUME_INFO_SIG:
                            self.volume_info = self.parse_volume_info(self.offset)

                        elif self.entry[self.offset:self.offset + 4] == BITMAP_SIG:
                            self.parse_bitmap_attr(self.offset)

                        elif self.entry[self.offset:self.offset + 4] == DATA_SIG:
                            self.data.append(self.parse_data(self.offset, fullParse, quickstat))

                        elif self.entry[self.offset:self.offset + 4] == INDEX_ROOT_SIG:
                            self.idx_root = self.parse_idx_root(self.offset)

                        elif self.entry[self.offset:self.offset + 4] == INDEX_ALLOC_SIG:
                            self.idx_alloc = self.parse_idx_alloc(self.offset)

                        elif self.entry[self.offset:self.offset + 4] == LOG_UTIL_STREAM_SIG:
                            self.parse_data(self.offset)
                            #self.log_util = self.parse_data(self.offset)

                        elif self.entry[self.offset:self.offset + 4] == END_OF_ENTRY_SIG:
                            break
                        else:
                            # Where the hell are we? Just go to the next entry...
                            break

                    # To Prevent NoneType Errors if a
                    # standard info attribute is not present.
                    """
                    if hasattr(self.std_info, 'ctime'):
                        ctime = self.std_info.ctime
                    if hasattr(self.std_info, 'mtime'):
                        mtime = self.std_info.mtime
                    if hasattr(self.std_info, 'atime'):
                        atime = self.std_info.atime
                    """
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
                    for data in self.data:
                        if data.name == None:
                            if hasattr(data, 'clusters') and len(data.clusters):
                                clusters = data.clusters
                            if hasattr(data, 'data_size'):
                                data_size = data.data_size
                            if hasattr(data, 'res_data') and data.res_data != None:
                                res_data = data.res_data
                            break
                    if name != None and 'DIRECTORY' in flags:
                            self.directories[self.entry_num] = (name, parent)
                    # We're not interested in MFT specific files nor deleted ones...
                    elif name != None and name[0] != '$' and self.header.flags != 0 and 'DIRECTORY' not in flags:
                        # FILE_RECORDs represent each file's metadata
                        if real_size == 0:
                            size = data_size
                        else:
                            size = real_size
                        self.entries.append(FILE_RECORD(name = name, entry_num = self.entry_num, parent = parent, size = size, clusters = clusters, res_data = res_data))
                    inode += 1
                    count += 1
                    if self.cleanup:
                        del(clusters)
                        del(self.data)
                        del(self.attr_list)
                else:
                    # We're not in an MFT Entry, move along now
                    count += 1
            except KeyboardInterrupt:
                print "User aborted"
                break

        if self.getFullPaths:
            for directory in self.directories:
                name = self.directories[directory][0]
                path = name
                parent = self.directories[directory][1]
                try:
                    while parent != 5:
                        path = self.directories[parent][0] + "/" + path
                        parent = self.directories[parent][1]
                    self.directories[directory] = (path, parent)
                except:
                    pass
            for entry in self.entries:
                parent = entry.parent
                entry.name = self.directories[parent][0] + '/' + entry.name
        del(self.directories)
        gc.collect()
        self.img.close()
        return self.entries


    def parse_header(self):
        """ Parse the Standard MFT Entry header. All entries should begin with this header. SHOULD.. """
        # First things first, we need to deal with the fixup values. Grab the saved values from the fixup
        # array and place them where they belong, namely the last 2 bytes of each sector.
        fix_arr_off = unpack("<H", self.entry[4:6])[0] + 2
        fix_arr_len = unpack("<H", self.entry[6:8])[0] + 1
        sec_end = self.sector_size - 2
        # Python strings are immutable...
        self.entry = list(self.entry)
        # For each sector in this entry, replace the fixup values with the original ones.
        for i in range(0, fix_arr_len, 2):
            self.entry[sec_end] = self.entry[fix_arr_off + i]
            self.entry[sec_end + 1] = self.entry[fix_arr_off + i + 1]
            sec_end += self.sector_size
        # Pack the list back into binary
        self.entry = pack("<1024c", *self.entry)
        lsn = unpack("<Q", self.entry[8:16])[0]
        seq_num = unpack("<H", self.entry[16:18])[0]
        # Number of references to file
        lnk_cnt = unpack("<H", self.entry[18:20])[0]
        # Should always be 56 (0x38) bytes from start of header
        # first_attr_off = unpack("<H", self.entry[20:22])[0]
        # Directory, System, Hidden, etc.
        flags = unpack("<H", self.entry[22:24])[0]
        # If mft_base != 0, then we're in an extended data attribute entry
        # owned by mft_base's entry. Its attributes could not fit in a single record
        # so another entry was reserved for it.
        mft_base = unpack("<Q", self.entry[32:40])[0] & 0x00FFFFFF
        # next_attr_id = unpack("<H", self.entry[40:42])[0]
        # MFT entry number, similar to an inode number
        entry_num = unpack("<I", self.entry[44:48])[0]
        self.entry_num = entry_num
        self.offset += MFT_HEADER_LEN
        # Return an object modeling the entry's standard header
        return MFT_STANDARD_HEADER(lsn = lsn, seq_num = seq_num, lnk_cnt = lnk_cnt, flags = flags, entry_num = entry_num, mft_base = mft_base)

    def parse_attr_list(self, offset):
        """Parse the Attribute List attribute of an entry. Entries only have an attribute list if a single entry is too small
           to hold all the metadata of the entry's attributes."""
        attr_list_len = unpack("<I", self.entry[offset + 4:offset + 8])[0]
        non_resident = unpack("<B", self.entry[offset + 8])[0]
        if non_resident == 0:
            return self.parse_attr_list_resident(offset, attr_list_len)
        else:
            return self.parse_attr_list_nonresident(offset, attr_list_len)

    def parse_attr_list_resident(self, offset, attr_list_len):
            attr_id = unpack("<H", self.entry[offset + 14:offset + 16])[0]
            attr_list = self.entry[offset + 24:offset + 24 + attr_list_len]
            offset = 0
            attr_entries = []
            while offset < attr_list_len - 24:
                attr_type = unpack("<I", attr_list[offset:offset + 4])[0]
                if attr_type == 0:
                    break
                attr_len = unpack("<H", attr_list[offset + 4:offset + 6])[0]
                name_len = unpack("<B", attr_list[offset + 6])[0]
                name_off = unpack("<B", attr_list[offset + 7])[0]
                start_vcn = unpack("<Q", attr_list[offset + 8:offset + 16])[0]
                mft_ref = unpack("<Q", attr_list[offset + 16:offset + 24])[0] & 0xFFFFFFFF
                attr_id = unpack("<B", attr_list[offset + 24])[0]
                name = attr_list[offset + name_off: offset + name_off + (2 * name_len)].replace('\x00', '')
                attr_entries.append(ATTR_LIST_ENTRY(attr_type = attr_type, attr_len = attr_len,
                    name_len = name_len, start_vcn = start_vcn, mft_ref = mft_ref, attr_id = attr_id, attr_name = name))
                offset += attr_len
            self.offset += attr_list_len
            return attr_entries

    def parse_attr_list_nonresident(self, offset, attr_list_len):
        #attr_id = unpack("<H", self.entry[offset + 14:offset + 16])[0]
        #start_vcn = unpack("<Q", self.entry[offset + 16:offset + 24])[0]
        #end_vcn = unpack("<Q", self.entry[offset + 24:offset + 32])[0]
        data_run_off = unpack("<H", self.entry[offset + 32:offset + 34])[0]
        #alloc_data_size = unpack("<Q", self.entry[offset + 40:offset + 48])[0]
        real_data_size = unpack("<Q", self.entry[offset + 48:offset + 56])[0]
        #init_data_size = unpack("<Q", self.entry[offset + 56:offset + 64])[0]
        data_run_len = unpack("<Q", self.entry[offset + 40:offset + 48])[0]
        data = self.entry[offset + data_run_off:offset + data_run_off + real_data_size]
        run_off = 0
        prev_data_runoffset = 0
        max_sign = [int(2 ** ((8 * x) - 1) - 1) for x in range(9)]
        file_fragmented = False
        attrs = []
        while True:
            tmp = b2a_hex(unpack("<c", data[run_off])[0])
            data_runoffset_bytes = int(tmp[0], 16)
            data_run_bytes = int(tmp[1], 16)
            if tmp[0] == '0' or tmp[1] == '0':
                break
            data = data[run_off + 1:]
            data_run_len = unpack("<Q", data[0:data_run_bytes % 8] + ('\x00' * (8 - (data_run_bytes % 8))))[0]
            data = data[data_run_bytes:]
            data_runoffset = unpack("<Q", data[0:data_runoffset_bytes] + ('\x00' * (8 - data_runoffset_bytes)))[0]
            data = data[data_runoffset_bytes:]
            if file_fragmented:
                    if max_sign[data_runoffset_bytes] >= data_runoffset:
                        data_runoffset += prev_data_runoffset
                    else:
                        data_runoffset = prev_data_runoffset - ((max_sign[data_runoffset_bytes] + 2) -
                                                               (data_runoffset - max_sign[data_runoffset_bytes]))
            for i in range(data_run_len):
                attrs.extend(self.parse_nonresident_attr_entries((data_runoffset + i) * self.cluster_size))
            if data[0] == DATA_RUN_END:
                break
            else:
                file_fragmented = True
                run_off = 0
                prev_data_runoffset = data_runoffset
                continue
        self.offset += attr_list_len
        return attrs


    def parse_nonresident_attr_entries(self, lcn):
        old_offset = self.img.tell()
        self.img.seek(lcn, os.SEEK_SET)
        attr_entry = self.img.read(self.cluster_size)
        self.img.seek(old_offset, os.SEEK_SET)
        attr_entries = []
        offset = 0
        while True:
            try:
                attr_type = unpack("<I", attr_entry[offset:offset + 4])[0]
                if attr_type == 0:
                    break
            except:
                return attr_entries
            attr_len = unpack("<H", attr_entry[offset + 4:offset + 6])[0]
            name_len = unpack("<B", attr_entry[offset + 6])[0]
            name_off = unpack("<B", attr_entry[offset + 7])[0]
            start_vcn = unpack("<Q", attr_entry[offset + 8:offset + 16])[0]
            mft_ref = unpack("<Q", attr_entry[offset + 16:offset + 24])[0] & 0xFFFFFFFF
            attr_id = unpack("<B", attr_entry[offset + 24])[0]
            name = attr_entry[offset + name_off: offset + name_off + (2 * name_len)].replace('\x00', '')
            attr_entries.append(ATTR_LIST_ENTRY(attr_type = attr_type, attr_len = attr_len,
                name_len = name_len, start_vcn = start_vcn, mft_ref = mft_ref, attr_id = attr_id, attr_name = name))
            offset += attr_len
        return attr_entries

    def parse_attr_list_entries(self, count):
        old_offset = self.offset
        old_entry = self.entry
        img_off = self.img.tell()
        for attr in self.attr_list:
            if attr.mft_ref != count:
                idx, vcn = math.modf((attr.mft_ref * MFT_ENTRY_SIZE) / self.cluster_size)
                idx = self.pos.index(idx)
                lcn = self.mft_data[int(vcn)]
                address = (lcn * self.cluster_size) + (idx * MFT_ENTRY_SIZE) + self.partoffset
                self.img.seek(address, os.SEEK_SET)
                self.entry = self.img.read(MFT_ENTRY_SIZE)
                self.parse_header()
                offset = MFT_HEADER_LEN
                if self.entry[offset:offset + 4] == DATA_SIG:
                    self.data.append(self.parse_data(offset, quickstat = False, fullParse = True))
                self.img.seek(img_off, os.SEEK_SET)
                self.offset = old_offset
                self.entry = old_entry
            else:
                offset = self.offset
                if self.entry[offset:offset + 4] == DATA_SIG:
                    self.data.append(self.parse_data(offset, quickstat = False, fullParse = True))
        return

    #def parse_attr_def(self, offset):
        #offset += 4
        #attr_name = self.entry[offset:offset+128]
        #type_id = unpack("<I", self.entry[offset+128:offset+132])[0]
        #display_rule = unpack("<I", self.entry[offset+132:offset+136])[0]
        #collation_rule = unpack("<I", self.entry[offset+136:offset+140])[0]
        #flags = unpack("<I", self.entry[offset+140:offset+144])[0]
        #min_size = unpack("<Q", self.entry[offset+144:offset+152])[0]
        #max_size = unpack("<Q", self.entry[offset+152:offset+160])[0]


    def parse_std_info(self, offset):
        std_info_len = unpack("<I", self.entry[offset + 4:offset + 8])[0]
        std_info = self.entry[offset + 24:offset + std_info_len]
        try:
            ctime = time.ctime((unpack("<Q", std_info[0:8])[0] - NTFS_EPOCH) / 10 ** (7))
            mtime = time.ctime((unpack("<Q", std_info[8:16])[0] - NTFS_EPOCH) / 10 ** (7))
            #mft_mod_time = time.ctime((unpack("<Q", std_info[16:24])[0] - NTFS_EPOCH) / 10**(7))
            atime = time.ctime((unpack("<Q", std_info[24:32])[0] - NTFS_EPOCH) / 10 ** (7))
        except:
            ctime = None
            mtime = None
            atime = None
        flags = unpack("<I", std_info[32:36])[0]
        attrs = [key for key in ATTRIBUTES if flags & ATTRIBUTES[key]]
        sid = None
        if std_info_len > 48:
            try:
                sid = unpack("<I", std_info[52:56])[0]
            except:
                pass
        self.offset += std_info_len
        return STANDARD_INFO(ctime = ctime, mtime = mtime, atime = atime, flags = attrs, sid = sid)

    def parse_filename(self, offset):
        attr_len = unpack("<I", self.entry[offset + 4:offset + 8])[0]
        filename = self.entry[offset + 24:offset + attr_len]
        parent = unpack("<Q", filename[0:8])[0] & 0x00FFFFFF
        try:
            ctime = time.ctime((unpack("<Q", filename[8:16])[0] - NTFS_EPOCH) / 10 ** (7))
            mtime = time.ctime((unpack("<Q", filename[16:24])[0] - NTFS_EPOCH) / 10 ** (7))
            #mft_mod_time = time.ctime((unpack("<Q", filename[24:32])[0] - NTFS_EPOCH) / 10**(7))
            atime = time.ctime((unpack("<Q", filename[32:40])[0] - NTFS_EPOCH) / 10 ** (7))
        except:
            ctime = None
            mtime = None
            atime = None
        alloc_size = unpack("<Q", filename[40:48])[0]
        real_size = unpack("<Q", filename[48:56])[0]
        flags = unpack("<I", filename[56:60])[0]
        attrs = [key for key in ATTRIBUTES if flags & ATTRIBUTES[key]]
        name_len = unpack("<B", filename[64])[0]
        namespace = unpack("<B", filename[65])[0]
        name = filename[66: 66 + (2 * name_len)].replace('\x00', '')
        self.offset += attr_len
        return FILENAME(parent = parent, ctime = ctime, mtime = mtime, atime = atime,
                 alloc_size = alloc_size, real_size = real_size, flags = attrs, name_len = name_len, name = name, namespace = namespace)

    def parse_object_id(self, offset):
        object_id = b2a_hex(self.entry[offset + 39:offset + 23:-1])
        object_id = '-'.join([object_id[0:8], object_id[8:12], object_id[12:16], object_id[16:20], object_id[20:]])
        self.offset += 40
        return OBJECT_ID(object_id)

    def parse_volume_name(self, offset):
        self.offset += unpack("<I", self.entry[offset + 4:offset + 8])[0]
        return None

    def parse_volume_info(self, offset):
        self.offset += unpack("<I", self.entry[offset + 4:offset + 8])[0]
        return None

    def parse_idx_root(self, offset):
        entry_len = unpack("<I", self.entry[offset + 4:offset + 8])[0]
        if not self.getIDXEntries:
            self.offset += entry_len
            return
        idx_root = self.entry[offset + 32:offset + 32 + entry_len]
        attr_type = idx_root[0:4]
        #coll_sort_rule = unpack("<I", idx_root[4:8])[0]
        #clusters_per_entry = int(b2a_hex(unpack("<c", idx_root[12])[0]), 16)
        idx_off = unpack("<I", idx_root[16:20])[0]
        idx_end = unpack("<I", idx_root[20:24])[0]
        #idx_alloc = unpack("<I", idx_root[24:28])[0]
        flags = unpack("<I", idx_root[28:32])[0]
        idx_entries = []
        idx_entry = idx_root[idx_off + 16:]
        offset = 0
        while True:
            mft_ref = unpack("<Q", idx_entry[offset:offset + 8])[0] & 0xFFFFFFFF
            idx_entry_len = unpack("<H", idx_entry[offset + 8:offset + 10])[0]
            filename_len = unpack("<H", idx_entry[offset + 10:offset + 12])[0]
            flags = unpack("<I", idx_entry[offset + 12:offset + 16])[0]
            if flags & 0x1 or mft_ref == 0:
                self.offset += entry_len
                return
            idx_record = self.parse_idx_entry_filename(idx_entry[offset + 16:offset + 16 + filename_len], filename_len)
            if idx_record == None:
                self.offset += entry_len
                return
            if idx_record.namespace == 2:
                offset += idx_entry_len
                continue
            idx_entries.append(idx_record)
            offset += idx_entry_len
            if flags & 0x2 or offset >= idx_end:
                break
        self.offset += entry_len
        return IDX_ROOT(attr_type = attr_type, idx_entries = idx_entries)

    def parse_idx_alloc(self, offset):
        idx_alloc_len = unpack("<I", self.entry[offset + 4:offset + 8])[0]
        if not self.getIDXEntries:
            self.offset += idx_alloc_len
            return
        #name_len = unpack("<B", self.entry[offset + 9])[0]
        #name_off = unpack("<H", self.entry[offset + 10:offset + 12])[0]
        #flags = unpack("<H", self.entry[offset + 12:offset + 14])[0]
        #attr_id = unpack("<H", self.entry[offset + 14:offset + 16])[0]
        #start_vcn = unpack("<Q", self.entry[offset + 16:offset + 24])[0]
        #end_vcn = unpack("<Q", self.entry[offset + 24:offset + 32])[0]
        data_run_off = unpack("<H", self.entry[offset + 32:offset + 34])[0]
        data_run_len = unpack("<Q", self.entry[offset + 40:offset + 48])[0]
        if data_run_len == 0:
            self.offset += idx_alloc_len
            return
        data = self.entry[offset + data_run_off:offset + data_run_off + data_run_len]
        entries = []
        run_off = 0
        prev_data_runoffset = 0
        max_sign = [int(2 ** ((8 * x) - 1) - 1) for x in range(9)]
        file_fragmented = False
        while True:
            tmp = b2a_hex(unpack("<c", data[run_off])[0])
            data_runoffset_bytes = int(tmp[0], 16)
            data_run_bytes = int(tmp[1], 16)
            if tmp[0] == '0' or tmp[1] == '0':
                break
            data = data[run_off + 1:]
            data_run_len = unpack("<Q", data[0:data_run_bytes % 8] + ('\x00' * (8 - (data_run_bytes % 8))))[0]
            data = data[data_run_bytes:]
            data_runoffset = unpack("<Q", data[0:data_runoffset_bytes] + ('\x00' * (8 - data_runoffset_bytes)))[0]
            data = data[data_runoffset_bytes:]
            if file_fragmented:
                    if max_sign[data_runoffset_bytes] >= data_runoffset:
                        data_runoffset += prev_data_runoffset
                    else:
                        data_runoffset = prev_data_runoffset - ((max_sign[data_runoffset_bytes] + 2) -
                                                               (data_runoffset - max_sign[data_runoffset_bytes]))
            for i in range(data_run_len):
                entries.extend(self.parse_idx_block((data_runoffset + i) * self.cluster_size))
            if data[0] == DATA_RUN_END:
                break
            else:
                file_fragmented = True
                run_off = 0
                prev_data_runoffset = data_runoffset
                continue
        self.offset += idx_alloc_len
        return IDX_ALLOC(entries)

    def parse_idx_block(self, lcn):
        old_offset = self.img.tell()
        self.img.seek(lcn, os.SEEK_SET)
        idx_block = self.img.read(self.cluster_size)
        self.img.seek(old_offset, os.SEEK_SET)
        fixup_arr_off = unpack("<H", idx_block[4:6])[0] + 2
        fixup_arr_len = unpack("<H", idx_block[6:8])[0] + 1
        #logfile_seq_num = unpack("<Q", idx_buffer[8:16])[0]
        #vcn = unpack("<Q", idx_block[16:24])[0]
        sec_end = self.sector_size - 2
        idx_block = list(idx_block)
        for i in range(0, fixup_arr_len, 2):
            idx_block[sec_end] = idx_block[fixup_arr_off + i]
            idx_block[sec_end + 1] = idx_block[fixup_arr_off + i + 1]
            sec_end += self.sector_size
        idx_block = pack("<%dc" % len(idx_block), *idx_block)
        idx_off = unpack("<I", idx_block[24:28])[0] + 24
        idx_end = unpack("<I", idx_block[28:32])[0] + 24
        #idx_alloc = unpack("<I", idx_block[32:36])[0] + 24
        #flags = unpack("<I", idx_block[36:40])[0]
        idx_entries = []
        entry = idx_block[idx_off:]
        offset = 0
        while offset < idx_end - 24:
            mft_ref = unpack("<Q", entry[offset:offset + 8])[0] & 0xFFFFFFFF
            entry_len = unpack("<H", entry[offset + 8:offset + 10])[0]
            filename_len = unpack("<H", entry[offset + 10:offset + 12])[0]
            #flags = unpack("<I", entry[offset + 12:offset + 16])[0]
            if mft_ref == 0:
                break
            idx_record = self.parse_idx_entry_filename(entry[offset + 16:offset + 16 + filename_len], filename_len)
            if idx_record == None:
                return idx_entries
            if idx_record.namespace == 2:
                offset += entry_len
                continue
            idx_entries.append(idx_record)
            offset += entry_len
        return idx_entries


    def parse_idx_entry_filename(self, entry, filename_len):
        try:
            idx_entry = entry[:filename_len]
            parent = unpack("<Q", idx_entry[0:8])[0] & 0x00FFFFFF
            try:
                ctime = time.ctime((unpack("<Q", idx_entry[8:16])[0] - NTFS_EPOCH) / 10 ** (7))
                mtime = time.ctime((unpack("<Q", idx_entry[16:24])[0] - NTFS_EPOCH) / 10 ** (7))
                #mft_mod_time = time.ctime((unpack("<Q", filename[24:32])[0] - NTFS_EPOCH) / 10 ** (7))
                atime = time.ctime((unpack("<Q", idx_entry[32:40])[0] - NTFS_EPOCH) / 10 ** (7))
            except:
                ctime = None
                mtime = None
                atime = None
            alloc_size = unpack("<Q", idx_entry[40:48])[0]
            real_size = unpack("<Q", idx_entry[48:56])[0]
            flags = unpack("<Q", idx_entry[56:64])[0]
            attrs = [key for key in ATTRIBUTES if flags & ATTRIBUTES[key]]
            name_len = unpack("<B", idx_entry[64])[0]
            namespace = unpack("<B", idx_entry[65])[0]
            filename = idx_entry[66: 66 + (2 * name_len)].replace('\x00', '')
            return FILENAME(parent = parent, ctime = ctime, mtime = mtime, atime = atime,
                     alloc_size = alloc_size, real_size = real_size, flags = attrs, name_len = name_len, name = filename, namespace = namespace)
        except:
            return None


    def parse_data(self, offset, fullParse = False, quickstat = True):
        clusters = []
        res_data = None
        name = None
        start_vcn = None
        end_vcn = None
        file_fragmented = False
        prev_data_runoffset = 0
        max_sign = [int(2 ** ((8 * x) - 1) - 1) for x in range(9)]
        data_len = unpack("<I", self.entry[offset + 4:offset + 8])[0]
        if quickstat:
            self.offset += data_len
            return
        data = self.entry[offset:offset + data_len]
        nonresident = int(b2a_hex(unpack("<c", data[8])[0]), 16)
        flags = unpack("<H", data[12:14])[0]
        attrs = [key for key in ATTRIBUTES if flags & ATTRIBUTES[key]]
        attr_id = unpack("<H", data[14:16])[0]
        if nonresident:
            start_vcn = unpack("<Q", data[16:24])[0]
            end_vcn = unpack("<Q", data[24:32])[0]
            run_off = unpack("<H", data[32:34])[0]
            alloc_size = unpack("<Q", data[40:48])[0]
            real_size = unpack("<Q", data[48:56])[0]
            while True:
                tmp = b2a_hex(unpack("<c", data[run_off])[0])
                data_runoffset_bytes = int(tmp[0], 16)
                data_run_bytes = int(tmp[1], 16)
                if tmp[0] == '0' or tmp[1] == '0':
                    break
                data = data[run_off + 1:]
                data_run_len = unpack("<Q", data[0:data_run_bytes % 8] + ('\x00' * (8 - (data_run_bytes % 8))))[0]
                data = data[data_run_bytes:]
                data_runoffset = unpack("<Q", data[0:data_runoffset_bytes] + ('\x00' * (8 - data_runoffset_bytes)))[0]
                data = data[data_runoffset_bytes:]
                if file_fragmented:
                    if max_sign[data_runoffset_bytes] >= data_runoffset:
                        data_runoffset += prev_data_runoffset
                    else:
                        data_runoffset = prev_data_runoffset - ((max_sign[data_runoffset_bytes] + 2) -
                                                               (data_runoffset - max_sign[data_runoffset_bytes]))
                clusters.append((data_runoffset, data_run_len))
                if data[0] == DATA_RUN_END:
                    break
                else:
                    file_fragmented = True
                    run_off = 0
                    prev_data_runoffset = data_runoffset
                    continue
        else:
            name_len = unpack("<B", data[9])[0]
            name_off = unpack("<H", data[10:12])[0]
            real_size = unpack("<I", data[12:16])[0]
            alloc_size = unpack("<I", data[16:20])[0]
            content_off = unpack("<H", data[20:22])[0]
            name = data[name_off:name_off + name_len]
            res_data = data[content_off:]
        self.offset += data_len
        if fullParse == True:
            return DATA(nonresident = nonresident, flags = attrs, attr_id = attr_id, start_vcn = start_vcn,
                        end_vcn = end_vcn, alloc_size = alloc_size, data_size = real_size, clusters = clusters,
                        file_fragmented = file_fragmented, res_data = res_data, name = name)
        elif fullParse == False and quickstat == False:
            return DATA(data_size = real_size, clusters = clusters, res_data = res_data)
        else:
            return DATA(data_size = real_size, clusters = [], res_data = res_data)

    def parse_bitmap_attr(self, offset):
        self.offset += unpack("<I", self.entry[offset + 4:offset + 8])[0]
        return None

    def parse_sec_desc(self, offset):
        self.offset += unpack("<I", self.entry[offset + 4:offset + 8])[0]
        return None

    def main(self):
        self.setup_mft_data()
        return self.parse_mft()
