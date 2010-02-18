#!/usr/bin/python
from __future__ import division
from mft import *
import os, sys, time, math
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

class MFT_Parser():
    def __init__(self, img=None):
        self.img = open(img, 'rb')
        self.entries = []
        self.mft_data = None
        self.sector_size = unpack('<H', self.img.read(0x0D)[-2:])[0]
        self.cluster_size = int(b2a_hex(unpack("<c", self.img.read(1))[0]),16) * self.sector_size
        self.num_sectors = unpack('<Q', self.img.read(0x22)[-8:])[0]
        self.num_bytes = self.num_sectors * self.sector_size
        self.num_clusters = self.num_bytes / self.cluster_size
        self.mft_base_offset = unpack("<Q", self.img.read(8))[0] * self.cluster_size

    def get_cluster_size(self):
        return self.cluster_size

    def get_img_size(self):
        return self.num_clusters

    def main(self):
        import psyco
        psyco.full()
        self.setup_mft_data()
        self.parse_mft()
        return self.entries

    def setup_mft_data(self):
        self.offset = self.mft_base_offset
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


    def parse_mft(self, start=0, end=99999999):
        count = start
        inode = start
        self.pos = [0.0, 0.25, 0.50, 0.75]
        self.dirs = {}
        while True:
            try:
                idx, vcn = math.modf((count * MFT_ENTRY_SIZE) / self.cluster_size)
                idx = self.pos.index(idx)
                if int(vcn) >= len(self.mft_data) or inode > end:
                    break
                lcn = self.mft_data[int(vcn)]
                address = (lcn * self.cluster_size) + (idx * MFT_ENTRY_SIZE)
                self.img.seek(address, os.SEEK_SET)
                self.entry = self.img.read(MFT_ENTRY_SIZE)
                self.offset = 0
                self.data = []
                clusters = []
                self.name_entries = {}
                self.std_info, self.filename, ads_data = None, None, None
                ctime, mtime, atime = None, None, None
                name, flags, parent, real_size, data_size = None, None, None, None, None
                if self.entry[0:4] == MFT_ENTRY_SIG:
                    """ Beginning of MFT Entry """
                    print "Entry: %i" % inode
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
                            self.data.append(self.parse_data(self.offset))

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
                        if 'DIRECTORY' in flags:
                           if name == '.':
                              name = 'RootDir'
                           self.dirs[inode] = name
                    if hasattr(self.filename, 'parent'):
                       parent = self.filename.parent
                       try:
                           parent = self.dirs[int(self.filename.parent)]
                       except:
                           parent = 'RootDir'
                    if hasattr(self.filename, 'real_size'):
                        real_size = self.filename.real_size
                    # And of course, for data attributes
                    for data in self.data:
                        if hasattr(data, 'clusters') and len(data.clusters):
                            clusters.extend(data.clusters)
                        if hasattr(data, 'ads_data'):
                            ads_data = data.ads_data
                        if hasattr(data, 'real_size'):
                            data_size = data.real_size

                    # We're not interested in MFT specific files nor deleted ones...
                    if name != None and name[0] != '$' and self.header.flags != 0:
                        # FILE_RECORDs represent each file's metadata
                        self.entries.append(FILE_RECORD(name=name, ctime=ctime, mtime=mtime,atime=atime, parent=parent,
                                                    real_size=real_size, data_size=data.real_size, clusters=clusters, ads_data=ads_data))
                    inode += 1
                    count += 1

                else:
                    # We're not in an MFT Entry, move along now
                    count += 1
            except KeyboardInterrupt:
                print "User aborted"
                break
        print "Processed %i MFT entries" % ((inode-1)-start)
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
                    address = (lcn * self.cluster_size) + (idx * MFT_ENTRY_SIZE)
                    self.img.seek(address, os.SEEK_SET)
                    self.entry = self.img.read(MFT_ENTRY_SIZE)
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
        ctime = time.ctime((unpack("<Q", std_info[0:8])[0] - NTFS_EPOCH) / 10**(7))
        mtime = time.ctime((unpack("<Q", std_info[8:16])[0] - NTFS_EPOCH) / 10**(7))
        #mft_mod_time = time.ctime((unpack("<Q", std_info[16:24])[0] - NTFS_EPOCH) / 10**(7))
        atime = time.ctime((unpack("<Q", std_info[24:32])[0] - NTFS_EPOCH) / 10**(7))
        flags = unpack("<I", std_info[32:36])[0]
        attrs = [key for key in ATTRIBUTES if flags & ATTRIBUTES[key]]
        self.offset += std_info_len
        return STANDARD_INFO(ctime=ctime, mtime=mtime, atime=atime, flags=attrs)

    def parse_filename(self, offset):
        attr_len = unpack("<I", self.entry[offset+4:offset+8])[0]
        filename = self.entry[offset+24:offset + attr_len]
        parent = unpack("<Q", filename[0:8])[0] & 0x00FFFFFF
        ctime = time.ctime((unpack("<Q", filename[8:16])[0] - NTFS_EPOCH) / 10**(7))
        mtime = time.ctime((unpack("<Q", filename[16:24])[0] - NTFS_EPOCH) / 10**(7))
        #mft_mod_time = time.ctime((unpack("<Q", filename[24:32])[0] - NTFS_EPOCH) / 10**(7))
        atime = time.ctime((unpack("<Q", filename[32:40])[0] - NTFS_EPOCH) / 10**(7))
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
        self.entry_len = unpack("<I", self.entry[offset+4:offset+8])[0]
        self.offset += self.entry_len
        return None
        # idx_root = self.entry[offset+32:offset+self.entry_len]
        # attr_type = idx_root[0:4]
        # coll_sort_rule = unpack("<I", idx_root[4:8])[0]
        # entry_size = unpack("<I", idx_root[8:12])[0]
        # node_header = idx_root[16:32]
        # node_header_off = offset+48
        # idx_list_off = unpack("<I", node_header[0:4])[0] + node_header_off
        # idx_used_end = unpack("<I", node_header[4:8])[0] + node_header_off
        # idx_alloc_end = unpack("<I", node_header[8:12])[0] + node_header_off
        # flags = unpack("<I", node_header[12:16])[0]
        #idx_entry = self.idx_entry(offset+64, idx_root[32:])
        # idx_entry = None
        # return IDX_ROOT(attr_type=attr_type, entry_len=self.entry_len, flags=flags, idx_entry=idx_entry)

    def parse_idx_alloc(self, offset):
        idx_alloc_len = unpack("<I", self.entry[offset+4:offset+8])[0]
        self.offset += idx_alloc_len
        return None
        # idx_header = self.entry[offset+4:offset+28]
        # sig = idx_header[0:4]
        # fixup_arr_off = unpack("<H", idx_header[4:6])[0]
        # fixup_arr_num = unpack("<H", idx_header[6:8])[0]
        # lsn = unpack("<Q", idx_header[8:16])[0]
        # vcn = unpack("<Q", idx_header[16:24])[0]
        # node_header_off = offset+28
        # node_header_end = node_header_off + 16
        # node_header = self.entry[node_header_off:node_header_end]
        # idx_list_off = unpack("<I", node_header[0:4])[0] + node_header_off
        # idx_used_end = unpack("<I", node_header[4:8])[0] + node_header_off
        # idx_alloc_end = unpack("<I", node_header[8:12])[0] + node_header_off
        # flags = unpack("<I", node_header[12:16])[0]
        # if fixup_arr_num > 0:
            # if fixup_arr_off == idx_list_off:
                # idx_list_off += fixup_arr_num * 2
        # idx_entries = []
        # num_entries = (idx_used_end - idx_list_off) / self.entry_len
        # count = 0
        # while count < num_entries:
            # entry = self.entry[idx_list_offset+(count * self.entry_len):
                            # idx_list_offset + (count * self.entry_len) + self.entry_len]
            # idx_offset = idx_list_offset + (count * self.entry_len)
            # child_vcn_off = (idx_offset + self.entry_len - 8) - ((idx_offset + self.entry_len - 8) % 8)
            # child_vcn = unpack("<Q", self.entry[child_vcn_off:child_vcn_off+8])[0]
            # idx_entries.append((self.idx_entry(idx_offset, entry), child_vcn))
            # count += 1

        # return IDX_ALLOC(sig=sig, lsn=lsn, vcn=vcn, flags=flags, idx_entries=idx_entries)

    # def parse_idx_entry(self, idx_offset, entry):
        # mft_file_ref = unpack("<Q", entry[0:8])[0]
        # entry_len = unpack("<H", entry[8:10])[0]
        # filename_attr_len = unpack("<H", entry[10:12])[0]
        # flags = unpack("<I", entry[12:16])[0]
        # if filename_attr_len > 0:
            # return self.parse_filename(idx_offset+16)


    def parse_data(self, offset):
        clusters = []
        ads_data = None
        name = None
        start_vcn = None
        end_vcn = None
        file_fragmented = False
        prev_data_run_offset = 0
        max_sign = [int(2**((8*x)-1)-1) for x in range(9)]
        data_len = unpack("<I", self.entry[offset+4:offset+8])[0]
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
                clusters.extend(range(data_run_offset, data_run_offset + data_run_len))
                #clusters.append((data_run_offset, data_run_offset + data_run_len-1))
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
            ads_data = data[content_off:]
        self.offset += data_len

        return DATA(nonresident=nonresident, flags=flags, attr_id=attr_id, start_vcn=start_vcn,
                end_vcn=end_vcn, alloc_size=alloc_size, real_size=real_size, clusters=clusters,
                file_fragmented=file_fragmented, ads_data=ads_data, name=name)

    def parse_bitmap_attr(self, offset):
        self.offset += unpack("<I", self.entry[offset+4:offset+8])[0]
        return None

    def parse_sec_desc(self, offset):
        self.offset += unpack("<I", self.entry[offset+4:offset+8])[0]
        return None

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
            print "Data Clusters: "
            print clusters
        if data.ads_data != None:
            print "ADS Data: "
            print data.ads_data
        print ''

if __name__ == "__main__":
    import psyco
    psyco.full()
    parser = MFT_Parser(sys.argv[1])
    parser.setup_mft_data()
    clusters = []
    end_vcn = 0
    if len(sys.argv) >= 3:
        if sys.argv[2] == '-p' or sys.argv[2] == '-d':
            parser.parse_mft(start=int(sys.argv[3]), end=int(sys.argv[3]))
            if sys.argv[2] == '-p':
                parser.print_header(parser)
                if hasattr(parser, 'std_info'):
                    if parser.std_info != None:
                        parser.print_std_info(parser)
                if hasattr(parser, 'filename'):
                    if parser.filename != None:
                        parser.print_filename(parser)
                if hasattr(parser, 'object_id'):
                    parser.print_object_id(parser)
            if sys.argv[2] == '-d':
                if len(parser.data):
                    start_vcn = parser.data[0].start_vcn
                    for i in range(len(parser.data)):
                        if parser.data[i].start_vcn != None and parser.data[i].start_vcn < start_vcn:
                            start_vcn = parser.data[i].start_vcn
                        if parser.data[i].end_vcn > end_vcn:
                            end_vcn = parser.data[i].end_vcn
                        if hasattr(parser.data[i], 'clusters'):
                            clusters.extend(parser.data[i].clusters)
                        ads_data = parser.data[i].ads_data
                    parser.print_data(parser.data[0], clusters, start_vcn, end_vcn)
        else:
            if len(sys.argv) == 3:
                parser.parse_mft(start=int(sys.argv[2]))
            if len(sys.argv) >= 4:
                parser.parse_mft(start=int(sys.argv[2]), end=int(sys.argv[3]))
    else:
        parser.parse_mft()

