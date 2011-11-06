
#!/usr/bin/python

from __future__ import division
from mft import *
import os, sys, time, math, gc
from struct import unpack, pack
from binascii import b2a_hex

MFT_ENTRY_SIZE =       0x400
MFT_HEADER_LEN =       0x38
MFT_ENTRY_SIG =       '\x46\x49\x4C\x45'
STANDARD_INFO_SIG =   '\x10\x00\x00\x00'
ATTR_LIST_SIG =       '\x20\x00\x00\x00'
FILENAME_SIG =        '\x30\x00\x00\x00'
OBJECT_ID_SIG =       '\x40\x00\x00\x00'
SECURITY_DESC_SIG =   '\x50\x00\x00\x00'
VOLUME_NAME_SIG =     '\x60\x00\x00\x00'
VOLUME_INFO_SIG =     '\x70\x00\x00\x00'
DATA_SIG =            '\x80\x00\x00\x00'
INDEX_ROOT_SIG =      '\x90\x00\x00\x00'
INDEX_ALLOC_SIG =     '\xA0\x00\x00\x00'
BITMAP_SIG =          '\xB0\x00\x00\x00'
LOG_UTIL_STREAM_SIG = '\x00\x01\x00\x00' #encryption key
END_OF_ENTRY_SIG =    '\xFF\xFF\xFF\xFF'
DATA_RUN_END =        '\x00'

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
    def __init__(self, img=None):
        self.img = open(img, 'rb')
        self.entries = []
        self.mft_data = None
        self.part_offset = None
        # Is the target a partition or an entire disk
        if unpack(">Q", self.img.read(0xB)[3:])[0] == NTFS_OEM_ID:
            # Partition
            self.part_offset = 0
        else:
            # Raw Disk:
            # Read starting sector for first partition from MBR
            self.part_offset = unpack("I", self.img.read(0x1BF)[-4:])[0] * 512
        self.img.seek(self.part_offset)
        """
        Grab FS data from the MBR
        """
        self.sector_size = unpack('<H', self.img.read(0x0D)[-2:])[0]
        self.cluster_size = int(b2a_hex(unpack("<c", self.img.read(1))[0]),16) * self.sector_size
        self.num_sectors = unpack('<Q', self.img.read(0x22)[-8:])[0]
        self.num_bytes = (self.num_sectors + 1) * self.sector_size
        self.num_clusters = int(math.ceil(self.num_bytes / self.cluster_size))
        self.mft_base_offset = unpack("<Q", self.img.read(8))[0] * self.cluster_size
        self.mft_mir_base_offset = unpack("<Q", self.img.read(8))[0] * self.cluster_size
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
        self.offset = self.mft_base_offset + self.part_offset
        self.img.seek(self.offset, os.SEEK_SET)
        self.entry = self.img.read(MFT_ENTRY_SIZE)
        self.offset = self.entry.find(DATA_SIG)
        data_len = unpack("<I", self.entry[self.offset+4:self.offset+8])[0]
        data = self.entry[self.offset:self.offset+data_len]
        run_off = unpack("<H", data[32:34])[0]
        prev_data_run_offset = 0
        self.mft_data = []
        max_sign = [int(2**((8*x)-1)-1) for x in range(9)]
        file_fragmented = False
        while True:
            try:
                tmp = b2a_hex(unpack("<c", data[run_off])[0])
                data_run_offset_bytes = int(tmp[0], 16)
                data_run_bytes = int(tmp[1], 16)
                if tmp[0] == '0' or tmp[1] == '0':
                    break
                data = data[run_off+1:]
                data_run_len = unpack("<Q", data[0:data_run_bytes] + ('\x00' * (8-data_run_bytes)))[0]
                data = data[data_run_bytes:]
                data_run_offset = unpack("<Q", data[0:data_run_offset_bytes] + ('\x00' * (8-data_run_offset_bytes)))[0]
                data = data[data_run_offset_bytes:]
                if file_fragmented:
                    if max_sign[data_run_offset_bytes] > data_run_offset:
                        data_run_offset += prev_data_run_offset
                    else:
                        data_run_offset = prev_data_run_offset - ((max_sign[data_run_offset_bytes] + 2) -
                                                                (data_run_offset - max_sign[data_run_offset_bytes]))
                self.mft_data.extend(range(data_run_offset, data_run_offset + data_run_len))
                if data[0] == DATA_RUN_END:
                    break
                else:
                    file_fragmented = True
                    run_off = 0
                    prev_data_run_offset = data_run_offset
            except:
                print 'Warning, error occurred while processing $MFT data, incomplete image perhaps?'

    def parse_mft(self, start=0, end=None, fullParse=False, quickstat=False, cleanup=True):
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
        self.dirs = {}
        self.fullParse = fullParse
        self.quickstat = quickstat
        self.cleanup = cleanup
        while True:
            try:
                idx, vcn = math.modf((count * MFT_ENTRY_SIZE) / self.cluster_size)
                idx = self.pos.index(idx)
                if int(vcn) >= len(self.mft_data) or (end != None and inode > end):
                    break
                lcn = self.mft_data[int(vcn)]
                address = (lcn * self.cluster_size) + (idx * MFT_ENTRY_SIZE) + self.part_offset
                self.img.seek(address, os.SEEK_SET)
                self.entry = self.img.read(MFT_ENTRY_SIZE)
                self.offset = 0
                self.data = []
                clusters = []
                self.std_info, self.filename, self.attr_list, res_data = None, None, None, None
                ctime, mtime, atime = None, None, None
                name, flags, parent, real_size, data_size, resident, size = None, None, None, None, None, None, 0
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
                        if self.entry[self.offset:self.offset+4] == STANDARD_INFO_SIG:
                            self.std_info = self.parse_std_info(self.offset)
                        
                        elif self.entry[self.offset:self.offset+4] == ATTR_LIST_SIG:
                            self.attr_list = self.parse_attr_list(self.offset)
                            self.parse_attr_list_entries(self.attr_list, inode)
                        
                        elif self.entry[self.offset:self.offset+4] == FILENAME_SIG:
                            filename = self.parse_filename(self.offset)
                            if self.filename != None:
                                if filename.namespace == 2:
                                    continue
                                else:
                                    self.filename = filename
                            else:
                                self.filename = filename
                        
                        elif self.entry[self.offset:self.offset+4] == OBJECT_ID_SIG:
                            self.object_id = self.parse_object_id(self.offset)
                        
                        elif self.entry[self.offset:self.offset+4] == SECURITY_DESC_SIG:
                            self.sec_desc = self.parse_sec_desc(self.offset)
                        
                        elif self.entry[self.offset:self.offset+4] == VOLUME_NAME_SIG:
                            self.volume_name = self.parse_volume_name(self.offset)
                        
                        elif self.entry[self.offset:self.offset+4] == VOLUME_INFO_SIG:
                            self.volume_info = self.parse_volume_info(self.offset)
                        
                        elif self.entry[self.offset:self.offset+4] == BITMAP_SIG:
                            self.parse_bitmap_attr(self.offset)
                        
                        elif self.entry[self.offset:self.offset+4] == DATA_SIG:
                            self.data.append(self.parse_data(self.offset, fullParse, quickstat))
                        
                        elif self.entry[self.offset:self.offset+4] == INDEX_ROOT_SIG:
                            self.idx_root = self.parse_idx_root(self.offset)
                        
                        elif self.entry[self.offset:self.offset+4] == INDEX_ALLOC_SIG:
                            self.idx_alloc = self.parse_idx_alloc(self.offset)
                        
                        elif self.entry[self.offset:self.offset+4] == LOG_UTIL_STREAM_SIG:
                           self.log_util = self.parse_data(self.offset)
                        
                        elif self.entry[self.offset:self.offset+4] == END_OF_ENTRY_SIG:
                            break
                        else:
                            # Where the hell are we? Just go to the next entry...
                            break
                    
                    # To Prevent NoneType Errors if a
                    # standard info attribute is not present.
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
                    # And of course, for data attributes
                    for data in self.data:
                        if hasattr(data, 'clusters') and len(data.clusters):
                            clusters.extend(data.clusters)
                        if hasattr(data, 'res_data') and data.res_data != None:
                            res_data = data.res_data
                        if hasattr(data, 'nonresident') and not data.nonresident:
                            resident = True
                        if hasattr(data, 'real_size'):
                            data_size = data.real_size

                    # We're not interested in MFT specific files nor deleted ones...
                    if name != None and name[0] != '$' and self.header.flags != 0 and 'DIRECTORY' not in self.filename.flags:
                        # FILE_RECORDs represent each file's metadata
                        if data_size == 0 or data_size == None:
                            size = real_size
                        else:
                            size = data_size
                        self.entries.append(FILE_RECORD(name=name, resident=resident, size=size, clusters=clusters, res_data=res_data))
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
        self.img.close()
        return self.entries

    
    def parse_header(self):
        """ Parse the Standard MFT Entry header. All entries should begin with this header. SHOULD.. """
        # First things first, we need to deal with the fixup values. Grab the saved values from the fixup
        # array and place them where they belong, namely the last 2 bytes of each sector.
        fix_arr_off = unpack("<H", self.entry[4:6])[0] + 2
        fix_arr_len = unpack("<H", self.entry[6:8])[0] + 1
        sec_end = self.sector_size-2
        # Python strings are immutable...
        self.entry = list(self.entry)
        # For each sector in this entry, replace the fixup values with the original ones.
        for i in range(0, fix_arr_len, 2):
            self.entry[sec_end] = self.entry[fix_arr_off+i]
            self.entry[sec_end+1] = self.entry[fix_arr_off+i+1]
            sec_end += self.sector_size
        # Pack the list back into binary
        self.entry = pack("<1024c", *self.entry)
        lsn = unpack("<Q", self.entry[8:16])[0]
        seq_num = unpack("<H", self.entry[16:18])[0]
        # Number of references to file
        lnk_cnt = unpack("<H", self.entry[18:20])[0]
        # Should always be 56 (0x38) bytes from start of header
        first_attr_off = unpack("<H", self.entry[20:22])[0]
        # Directory, System, Hidden, etc.
        flags = unpack("<H", self.entry[22:24])[0]
        # If mft_base != 0, then we're in an extended data attribute entry
        # owned by mft_base's entry. Its attributes could not fit in a single record
        # so another entry was reserved for it.
        mft_base = unpack("<Q", self.entry[32:40])[0] & 0x00FFFFFF
        next_attr_id = unpack("<H", self.entry[40:42])[0]
        # MFT entry number, similar to an inode number
        entry_num = unpack("<I", self.entry[44:48])[0]
        self.offset += MFT_HEADER_LEN
        # Return an object modeling the entry's standard header
        return MFT_STANDARD_HEADER(lsn=lsn, seq_num=seq_num, lnk_cnt=lnk_cnt, flags=flags, entry_num=entry_num, mft_base=mft_base)
    
    def parse_attr_list(self, offset):
        """Parse the Attribute List attribute of an entry. Entries only have an attribute list if a single entry is too small
           to hold all the metadata of the entry's attributes."""
        attrs = []
        attr_list_len = unpack("<I", self.entry[offset+16:offset+20])[0]
        offset += 24
        self.offset = offset
        attr_list_end = offset + attr_list_len
        while offset < attr_list_end:
            attr_type = unpack("<I", self.entry[offset:offset+4])[0]
            entry_len = unpack("<H", self.entry[offset+4:offset+6])[0]
            entry_name_len = int(b2a_hex(unpack("<c", self.entry[offset+6])[0]),16)
            name_off = int(b2a_hex(unpack("<c", self.entry[offset+7])[0]), 16)
            start_vcn = unpack("<Q", self.entry[offset+8:offset+16])[0]
            mft_entry = unpack("<Q", self.entry[offset+16:offset+24])[0] & 0x00FFFFFF
            attr_id = int(b2a_hex(unpack("<c", self.entry[offset+24])[0]),16)
            attrs.append(ATTR_LIST(attr_type=attr_type, entry_len=entry_len, entry_name_len=entry_name_len,
                    start_vcn=start_vcn, mft_entry=mft_entry, attr_id=attr_id))
            offset += entry_len
            self.offset = offset
        return attrs
    
    def parse_attr_list_entries(self, attr_list, count):
        old_offset = self.offset
        old_entry = self.entry
        img_off = self.img.tell()
        entry_off = {}
        for attr in attr_list:
            if attr.mft_entry not in entry_off:
                entry_off[attr.mft_entry] = MFT_HEADER_LEN
            if attr.attr_type == 128 or attr.attr_type == 48:
                if attr.mft_entry != count:
                    idx, vcn = math.modf((attr.mft_entry * MFT_ENTRY_SIZE) / self.cluster_size)
                    idx = self.pos.index(idx)
                    lcn = self.mft_data[int(vcn)]
                    address = (lcn * self.cluster_size) + (idx * MFT_ENTRY_SIZE) + self.part_offset
                    self.img.seek(address, os.SEEK_SET)
                    self.entry = self.img.read(MFT_ENTRY_SIZE)
                    self.parse_header()
                    offset = entry_off[attr.mft_entry]
                    if self.entry[offset:offset+4] == FILENAME_SIG:
                        self.filename = self.parse_filename(offset)
                        entry_off[attr.mft_entry] = self.offset
                    elif self.entry[offset:offset+4] == DATA_SIG:
                        self.data.append(self.parse_data(offset))
                        entry_off[attr.mft_entry] = self.offset
        self.img.seek(img_off, os.SEEK_SET)
        self.offset = old_offset
        self.entry = old_entry
        return None
    
    def parse_attr_def(self, offset):
        offset += 4
        attr_name = self.entry[offset:offset+128]
        type_id = unpack("<I", self.entry[offset+128:offset+132])[0]
        display_rule = unpack("<I", self.entry[offset+132:offset+136])[0]
        collation_rule = unpack("<I", self.entry[offset+136:offset+140])[0]
        flags = unpack("<I", self.entry[offset+140:offset+144])[0]
        min_size = unpack("<Q", self.entry[offset+144:offset+152])[0]
        max_size = unpack("<Q", self.entry[offset+152:offset+160])[0]

    
    def parse_std_info(self, offset):
        std_info_len = unpack("<I", self.entry[offset+4:offset+8])[0]
        std_info = self.entry[offset+24:offset + std_info_len]
        try:
            ctime = time.ctime((unpack("<Q", std_info[0:8])[0] - NTFS_EPOCH) / 10**(7))
            mtime = time.ctime((unpack("<Q", std_info[8:16])[0] - NTFS_EPOCH) / 10**(7))
            #mft_mod_time = time.ctime((unpack("<Q", std_info[16:24])[0] - NTFS_EPOCH) / 10**(7))
            atime = time.ctime((unpack("<Q", std_info[24:32])[0] - NTFS_EPOCH) / 10**(7))
        except:
            ctime = None
            mtime = None
            atime = None
        flags = unpack("<I", std_info[32:36])[0]
        attrs = [key for key in ATTRIBUTES if flags & ATTRIBUTES[key]]
        self.offset += std_info_len
        return STANDARD_INFO(ctime=ctime, mtime=mtime, atime=atime, flags=attrs)
    
    def parse_filename(self, offset):
        attr_len = unpack("<I", self.entry[offset+4:offset+8])[0]
        filename = self.entry[offset+24:offset + attr_len]
        parent = unpack("<Q", filename[0:8])[0] & 0x00FFFFFF
        try:
            ctime = time.ctime((unpack("<Q", filename[8:16])[0] - NTFS_EPOCH) / 10**(7))
            mtime = time.ctime((unpack("<Q", filename[16:24])[0] - NTFS_EPOCH) / 10**(7))
            #mft_mod_time = time.ctime((unpack("<Q", filename[24:32])[0] - NTFS_EPOCH) / 10**(7))
            atime = time.ctime((unpack("<Q", filename[32:40])[0] - NTFS_EPOCH) / 10**(7))
        except:
            ctime = None
            mtime = None
            atime = None
        self.alloc_size = unpack("<Q", filename[40:48])[0]
        self.real_size = unpack("<Q", filename[48:56])[0]
        flags = unpack("<I", filename[56:60])[0]
        attrs = [key for key in ATTRIBUTES if flags & ATTRIBUTES[key]]
        name_len = int(b2a_hex(unpack("<c", filename[64])[0]), 16)
        namespace = int(b2a_hex(unpack("<c", filename[65])[0]), 16)
        name = filename[66: 66 + (2 * name_len)].replace('\x00', '')
        self.offset += attr_len
        return FILENAME(parent=parent, ctime=ctime, mtime=mtime, atime=atime,
                 alloc_size=self.alloc_size, real_size=self.real_size, flags=attrs, name_len=name_len, name=name, namespace=namespace)
    
    def parse_object_id(self, offset):
        object_id = b2a_hex(self.entry[offset+39:offset+23:-1])
        object_id = '-'.join([object_id[0:8], object_id[8:12], object_id[12:16], object_id[16:20], object_id[20:]])
        self.offset += 40
        return OBJECT_ID(object_id)
    
    def parse_volume_name(self, offset):
        self.offset += unpack("<I", self.entry[offset+4:offset+8])[0]
        return None
    
    def parse_volume_info(self, offset):
        self.offset += unpack("<I", self.entry[offset+4:offset+8])[0]
        return None
    
    def parse_idx_root(self, offset):
        entry_len = unpack("<I", self.entry[offset+4:offset+8])[0]
        if not self.fullParse:
            self.offset += entry_len
            return
        idx_root = self.entry[offset+32:offset+32+entry_len]
        attr_type = idx_root[0:4]
        coll_sort_rule = unpack("<I", idx_root[4:8])[0]
        self.idx_alloc_entry_size = unpack("<I", idx_root[8:12])[0]
        self.clusters_per_entry = int(b2a_hex(unpack("<c", idx_root[12])[0]),16)
        idx_entry_list_off = unpack("<I", idx_root[16:20])[0]
        end_entry_list_off = unpack("<I", idx_root[20:24])[0]
        end_entry_alloc_off = unpack("<I", idx_root[24:28])[0]
        idx_entry_flags = unpack("<I", idx_root[28:32])[0]
        idx_entries=[]
        idx_entry = idx_root[idx_entry_list_off+16:]
        offset = 0
        while True:
            mft_ref = unpack("<Q", idx_entry[offset:offset+8])[0] & 0xFFFFFFFF
            idx_entry_len = unpack("<H", idx_entry[offset+8:offset+10])[0]
            filename_len = unpack("<H", idx_entry[offset+10:offset+12])[0]
            flags = unpack("<I", idx_entry[offset+12:offset+16])[0]
            if filename_len:
                filename, namespace = self.parse_idx_entry_filename(idx_entry[offset+16:offset+16+filename_len], filename_len)
                if namespace == 2:
                    offset += idx_entry_len
                    continue
                else:
                    idx_entries.append((filename, int(mft_ref)))
            offset += idx_entry_len
            if flags & 0x2 or offset >= end_entry_list_off:
                break
        self.offset += entry_len
        return IDX_ROOT(attr_type=attr_type, idx_entries=idx_entries)
    
    def parse_idx_alloc(self, offset):
        idx_alloc_len = unpack("<I", self.entry[offset+4:offset+8])[0]
        if not self.fullParse:
            self.offset += idx_alloc_len
            return
        self.original_offset = self.img.tell()
        idx_alloc = self.entry[offset+32:offset+32+idx_alloc_len]
        idx_list_off = unpack("<I", idx_alloc[0:4])[0]
        idx_end_used = unpack("<I", idx_alloc[4:8])[0]
        idx_end_alloc = unpack("<I", idx_alloc[8:12])[0]
        idx_entry_flags = unpack("<I", idx_alloc[12:16])[0]
        data_run_len = idx_alloc_len - idx_list_off
        data_run = idx_alloc[idx_list_off-32:]
        entries = []
        run_off = 0
        prev_data_run_offset = 0
        max_sign = [int(2**((8*x)-1)-1) for x in range(9)]
        file_fragmented = False
        while True:
            tmp = b2a_hex(unpack("<c", data_run[run_off])[0])
            data_run_offset_bytes = int(tmp[0], 16)
            data_run_bytes = int(tmp[1], 16)
            if tmp[0] == '0' or tmp[1] == '0':
                break
            data_run = data_run[run_off+1:]
            data_run_len = unpack("<Q", data_run[0:data_run_bytes] + ('\x00' * (8-data_run_bytes)))[0]
            data_run = data_run[data_run_bytes:]
            data_run_offset = unpack("<Q", data_run[0:data_run_offset_bytes] + ('\x00' * (8-data_run_offset_bytes)))[0]
            data_run = data_run[data_run_offset_bytes:]
            if file_fragmented:
                if max_sign[data_run_offset_bytes] > data_run_offset:
                    data_run_offset += prev_data_run_offset
                else:
                    data_run_offset = prev_data_run_offset - ((max_sign[data_run_offset_bytes] + 2) -
                                                              (data_run_offset - max_sign[data_run_offset_bytes]))
            entries.extend(self.parse_idx_entry_nonresident(data_run_offset * self.cluster_size))
            if data_run[0] == DATA_RUN_END:
                break
            else:
                file_fragmented = True
                run_off = 0
                prev_data_run_offset = data_run_offset
                continue
        self.img.seek(self.original_offset, os.SEEK_SET)
        self.offset += idx_alloc_len
        return IDX_ALLOC(entries)

    
    def parse_idx_entry_nonresident(self, lcn):
        self.img.seek(lcn, os.SEEK_SET)
        idx_entry = self.img.read(4096)
        fixup_arr_off = unpack("<H", idx_entry[4:6])[0] + 2
        fixup_arr_len = unpack("<H", idx_entry[6:8])[0] + 1
        logfile_seq_num = unpack("<Q", idx_entry[8:16])[0]
        idx_stream_vcn = unpack("<Q", idx_entry[16:24])[0]
        sec_end = self.sector_size-2
        idx_entry = list(idx_entry)
        for i in range(0, fixup_arr_len, 2):
            try:
                idx_entry[sec_end] = idx_entry[fixup_arr_off+i]
                idx_entry[sec_end+1] = idx_entry[fixup_arr_off+i+1]
                sec_end += self.sector_size
            except:
                pass
        idx_entry = pack("<%dc" % self.idx_alloc_entry_size, *idx_entry)
        idx_list_off = unpack("<I", idx_entry[24:28])[0] + 24
        idx_end_used = unpack("<I", idx_entry[28:32])[0] + 24
        idx_end_alloc = unpack("<I", idx_entry[32:36])[0] + 24
        idx_entry_flags = unpack("<I", idx_entry[36:40])[0]
        file_entries = []
        entry = idx_entry[idx_list_off:]
        offset = 0
        while True:
            mft_ref = unpack("<Q", entry[offset:offset+8])[0] & 0xFFFFFFFF
            entry_len = unpack("<H", entry[offset+8:offset+10])[0]
            filename_len = unpack("<H", entry[offset+10:offset+12])[0]
            flags = unpack("<I", entry[offset+12:offset+16])[0]
            if filename_len:
                filename, namespace = self.parse_idx_entry_filename(entry[offset+16:offset+16+filename_len], filename_len)
                if namespace == 2:
                    offset += entry_len
                    continue
                else:
                    file_entries.append((filename, int(mft_ref)))
            offset += entry_len
            if flags & 0x2 or offset >= idx_end_used:
                break
        return file_entries
    
    '''
    def parse_idx_entry_filename(self, entry, filename_len):
        filename = entry[0:filename_len]
        parent = unpack("<Q", filename[0:8])[0] & 0x00FFFFFF
        try:
             ctime = time.ctime((unpack("<Q", filename[8:16])[0] - NTFS_EPOCH) / 10**(7))
             mtime = time.ctime((unpack("<Q", filename[16:24])[0] - NTFS_EPOCH) / 10**(7))
             #mft_mod_time = time.ctime((unpack("<Q", filename[24:32])[0] - NTFS_EPOCH) / 10**(7))
             atime = time.ctime((unpack("<Q", filename[32:40])[0] - NTFS_EPOCH) / 10**(7))
        except:
             ctime = None
             mtime = None
             atime = None
        alloc_size = unpack("<Q", filename[40:48])[0]
        real_size = unpack("<Q", filename[48:56])[0]
        flags = unpack("<I", filename[56:60])[0]
        attrs = [key for key in ATTRIBUTES if flags & ATTRIBUTES[key]]
        name_len = int(b2a_hex(unpack("<c", filename[64])[0]), 16)
        namespace = int(b2a_hex(unpack("<c", filename[65])[0]), 16)
        return FILENAME(parent=parent, ctime=ctime, mtime=mtime, atime=atime,
                 alloc_size=alloc_size, real_size=real_size, flags=attrs, name_len=name_len, name=name, namespace=namespace)
    '''
    def parse_idx_entry_filename(self, entry, filename_len):
        try:
            filename = entry[0:filename_len]
            name_len = int(b2a_hex(unpack("<c", filename[64])[0]), 16)
            namespace = int(b2a_hex(unpack("<c", filename[65])[0]), 16)
            return (filename[66: 66 + (2 * name_len)].replace('\x00', ''), namespace)
        except:
            return None, None

    def parse_data(self, offset, fullParse=False, quickstat=True):
        clusters = []
        res_data = None
        name = None
        start_vcn = None
        end_vcn = None
        file_fragmented = False
        prev_data_run_offset = 0
        max_sign = [int(2**((8*x)-1)-1) for x in range(9)]
        data_len = unpack("<I", self.entry[offset+4:offset+8])[0]
        if quickstat:
            self.offset += data_len
            return
        data = self.entry[offset:offset+data_len]
        nonresident = int(b2a_hex(unpack("<c", data[8])[0]), 16)
        flags = unpack("<H", data[12:14])[0]
        attr_id = unpack("<H", data[14:16])[0]
        if nonresident:
            start_vcn = unpack("<Q", data[16:24])[0]
            end_vcn = unpack("<Q", data[24:32])[0]
            run_off = unpack("<H", data[32:34])[0]
            alloc_size = unpack("<Q", data[40:48])[0]
            real_size = unpack("<Q", data[48:56])[0]
            while True:
                tmp = b2a_hex(unpack("<c", data[run_off])[0])
                data_run_offset_bytes = int(tmp[0], 16)
                data_run_bytes = int(tmp[1], 16)
                if tmp[0] == '0' or tmp[1] == '0':
                    break
                data = data[run_off+1:]
                try:
                    data_run_len = unpack("<Q", data[0:data_run_bytes%8] + ('\x00' * (8-(data_run_bytes%8))))[0]
                except:
                    print "Error: Could not parse all data clusters for file"
                    sys.exit(-1)
                data = data[data_run_bytes:]
                data_run_offset = unpack("<Q", data[0:data_run_offset_bytes] + ('\x00' * (8-data_run_offset_bytes)))[0]
                data = data[data_run_offset_bytes:]
                if file_fragmented:
                    if max_sign[data_run_offset_bytes] > data_run_offset:
                        data_run_offset += prev_data_run_offset
                    else:
                        data_run_offset = prev_data_run_offset - ((max_sign[data_run_offset_bytes] + 2) -
                                                               (data_run_offset - max_sign[data_run_offset_bytes]))
                clusters.extend(range(data_run_offset, data_run_offset + data_run_len))
                #clusters =append(clusters, range(data_run_offset, data_run_offset + data_run_len))
                if data[0] == DATA_RUN_END:
                    break
                else:
                    file_fragmented = True
                    run_off = 0
                    prev_data_run_offset = data_run_offset
                    continue
        else:
            name_len = int(b2a_hex(unpack("<c", data[9])[0]), 16)
            name_off = unpack("<H", data[10:12])[0]
            real_size = unpack("<I", data[16:20])[0]
            alloc_size = unpack("<I", data[16:20])[0]
            content_off = unpack("<H", data[20:22])[0]
            name = data[name_off:name_off + name_len]
            res_data = data[content_off:]
        self.offset += data_len
        if fullParse == True:
            return DATA(nonresident=nonresident, flags=flags, attr_id=attr_id, start_vcn=start_vcn,
                        end_vcn=end_vcn, alloc_size=alloc_size, real_size=real_size, clusters=clusters,
                        file_fragmented=file_fragmented, res_data=res_data, name=name)
        elif fullParse == False and quickstat == False:
            return PDATA(data_size=real_size, clusters=clusters, res_data=res_data)
        else:
            return PDATA(data_size=real_size, clusters=[], res_data=res_data)
    
    def parse_bitmap_attr(self, offset):
        self.offset += unpack("<I", self.entry[offset+4:offset+8])[0]
        return None
    
    def parse_sec_desc(self, offset):
        self.offset += unpack("<I", self.entry[offset+4:offset+8])[0]
        return None
    
    def getFiletypeStats(self):
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
        for entry in self.entries:
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
            if i == 9:
                filestats['other'].append(entry.name)
        print "Finished analysing files.\n"
        print "Number of files: %i" % len(self.entries)
        print "video      : %i" % len(filestats['video'])
        print "images     : %i" % len(filestats['image'])
        print "audio      : %i" % len(filestats['audio'])
        print "binaries   : %i" % len(filestats['binaries'])
        print "text       : %i" % len(filestats['text'])
        print "compressed : %i" % len(filestats['compressed'])
        print "system     : %i" % len(filestats['system'])
        print "other      : %i" % len(filestats['other'])
        if len(sys.argv) >= 4:
            ftype = sys.argv[3].lower()
            if ftype in filestats:
                print "\n********** Listing of %s files **********" % ftype
                for f in filestats[ftype]:
                    print f
    
    def print_header(self, parser):
        print "*****************HEADER INFO*****************"
        print "Entry:                           %i" % parser.header.entry_num
        print "$Logfile seq number:             %i" % parser.header.lsn
        print "MFT Base Record:                 %i" % parser.header.mft_base
        print "Allocation status:              ",
        if parser.header.flags != 0:
            print "Allocated"
        else:
            print "Unallocated/Deleted"
        print "Links:                           %i" % parser.header.lnk_cnt
        print ''
    
    def print_std_info(self, parser):
        print "****************STANDARD INFO****************"
        print "Flags:   ",
        print parser.std_info.flags
        print "Created:             %s" % parser.std_info.ctime
        print "File Modified:       %s" % parser.std_info.mtime
        print "Accessed:            %s" % parser.std_info.atime
        print ''
    
    def print_filename(self, parser):
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
    
    def print_object_id(self, parser):
        print "******************OBJECT ID******************"
        print "Object ID: %s" % parser.object_id.object_id.upper()
        print ''
    
    def print_idx_root(self, parser):
        print "*****************INDEX ROOT**************"
        print parser.idx_root.idx_entries
        print ''

    
    def print_idx_alloc(self, parser):
        print "*****************INDEX ALLOCATION**************"
        print parser.idx_alloc.idx_entries
        print ''

    
    def print_data(self, data, clusters, start_vcn, end_vcn):
        print "******************DATA INFO******************"
        print "Attribute ID:                    %i" % data.attr_id
        print "Attribute Name:                  %s" % data.name
        print "Flags:                           %i" % data.flags
        print "Allocated size:                  %i" % data.alloc_size
        print "Actual size:                     %i" % data.real_size
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
        if data.clusters != None:
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
    
    def print_fsdata(self, parser):
        print "******************FS INFO******************"
        print "Volume Type: NTFS"
        print "Volume Serial Number: %s" % str(self.serial_num)[2:-1].upper()
        print "Volume Size: %i" % self.num_bytes
        print "Sector Size: %i" % self.sector_size
        print "Cluster Size: %i" % self.cluster_size
        print "Number of Sectors: %i" % (self.num_bytes / self.sector_size)
        print "Number of Clusters: %i" % self.num_clusters
        print "MFT Entry Size(Bytes): %i" % MFT_ENTRY_SIZE
        print "$MFT Offset(Bytes): %i" % self.mft_base_offset
        print "$MFT Offset(Clusters): %i" % (self.mft_base_offset / self.cluster_size)
        print "$MFTMIR Offset(Bytes): %i" % self.mft_mir_base_offset
        print "$MFTMIR Offset(Clusters): %i" % (self.mft_mir_base_offset / self.cluster_size)
        #print "Number of files on volume: %i" % len(self.entries)
    
    def cluster_to_file(self, parser, clusters):
        for cluster in clusters:
            allocated = 0
            cluster = int(cluster)
            for entry in parser.entries:
                if cluster in entry.clusters:
                    print("Cluster: %s maps to file: %s" % (cluster, entry.name))
                    allocated = 1
                    break
            if not allocated:
                print("Cluster %s unallocated" % cluster)
    
    def main(self):
        try:
            import psyco
            psyco.full()
        except:
            pass
        self.setup_mft_data()
        self.parse_mft()
        return self.entries


if __name__ == "__main__":
    import argparse
    try:
        import psyco
        psyco.full()
    except:
        pass

    argparser = argparse.ArgumentParser(description="""
    Parses the MFT of an NTFS filesystem. The data returned depends on the flags selected by the user. Optional functionality similar to Sleuthkit's fsstat/istat is possible, as well as a tentative count of various file-types found throughout the system. Note: When using this option, the file-type is determined exclusively by extension, so counts may not truly reflect the contents of the system. The command-line functions are only "extra-functionality", as the main purpose of this tool is to be used by an "image reader", to parse and return serializable MFT entry objects, each representing a unique file on the file-system. Each object can be used, in conjunction with its raw data blocks, to recreate the file it represents on the fly.
    """)
    argparser.add_argument('-i', '--image', help="Target image/drive to be parsed.", required=True)
    group = argparser.add_mutually_exclusive_group(required=True)
    group.add_argument('-e', '--entry', type=int, help="Get basic MFT entry data for supplied entry number. Similar to Sleuthkit's istat sans datarun info for ease of viewing. See -d/--data for datarun listings.")
    group.add_argument('-d', '--data', type=int, help="Get data blocks belonging to file in specified MFT entry.")
    group.add_argument('-c', '--count', help="Get a summary count of various file-types found on the filesystem.", action='store_true')
    group.add_argument('-f', '--fsinfo', help="Get basic volume information. Similar to Sleuthkit's fsstat.", action='store_true')
    args = argparser.parse_args()
    parser = MFTParser(args.image)
    parser.setup_mft_data()
    opts = vars(args)
    
    if opts['entry'] or opts['data']:
        try:
            entry_num = int(opts['entry'])
        except:
            entry_num = int(opts['data'])
        if entry_num > max(parser.mft_data):
            print "Specified entry number %d is invalid. Please specify a value between 0-%d" % (entry_num, max(parser.mft_data))
            sys.exit(-1)
        else:
            parser.parse_mft(start=entry_num, end=entry_num, fullParse=True, cleanup=False)
    if opts['entry']:
        if hasattr(parser, 'header') and parser.header != None:
            parser.print_header(parser)
        if hasattr(parser, 'std_info') and parser.std_info != None:
            parser.print_std_info(parser)
        if hasattr(parser, 'filename') and parser.filename != None:
            parser.print_filename(parser)
        if hasattr(parser, 'object_id'):
            parser.print_object_id(parser)
        if hasattr(parser, 'idx_root'):
            parser.print_idx_root(parser)
        if hasattr(parser, 'idx_alloc'):
            parser.print_idx_alloc(parser)
    elif opts['data']:
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
            parser.print_data(parser.data[0], clusters, start_vcn, end_vcn)
    elif opts['count']:
        print time.ctime()
        parser.parse_mft(fullParse=False, quickstat=True)
        parser.getFiletypeStats()
        print time.ctime()
    elif opts['fsinfo']:
        parser.print_fsdata(parser)