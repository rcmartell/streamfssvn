#!/usr/bin/python

from mft import *
import os, math, array
from struct import *
from binascii import b2a_hex
from functools import reduce

MFT_ENTRY_SIZE = 0x400
MFT_HEADER_LEN = 0x38
MFT_ENTRY_SIG = b'\x46\x49\x4C\x45'
STANDARD_INFO_SIG = b'\x10\x00\x00\x00'
ATTR_LIST_SIG = b'\x20\x00\x00\x00'
FILENAME_SIG = b'\x30\x00\x00\x00'
OBJECT_ID_SIG = b'\x40\x00\x00\x00'
SECURITY_DESC_SIG = b'\x50\x00\x00\x00'
VOLUME_NAME_SIG = b'\x60\x00\x00\x00'
VOLUME_INFO_SIG = b'\x70\x00\x00\x00'
DATA_SIG = b'\x80\x00\x00\x00'
INDEX_ROOT_SIG = b'\x90\x00\x00\x00'
INDEX_ALLOC_SIG = b'\xA0\x00\x00\x00'
BITMAP_SIG = b'\xB0\x00\x00\x00'
LOG_UTIL_STREAM_SIG = b'\x00\x01\x00\x00' #encryption key
END_OF_ENTRY_SIG = b'\xFF\xFF\xFF\xFF'
DATA_RUN_END = b'\x00'

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
def from_bytes(x): return int.from_bytes(x, 'little')
def s_from_bytes(x): return int.from_bytes(x, 'little', signed=True)
def to_bytes(x, y): return x.to_bytes(y, 'little')
def to_signed(x, y): return x | ~(2**(y*8)-1) if x & (1 << ((y*8)-1)) else x
BITMASKS = {
        'Byte'              : 0xFF,
        'Short'             : 0xFFFF,
        'Int'               : 0xFFFFFFFF,
        'Long'              : 0xFFFFFFFFFFFF
    }
class MFTParser():
    def __init__(self, path = None, partition = 0):
        self.fh = open(path, 'rb')
        self.entry = bytearray(MFT_ENTRY_SIZE)
        self.entries = []
        self.mft_data = None
        self.part_offset = 0
        if partition == 0:
            if unpack(">Q", self.fh.read(0xB)[3:])[0] != NTFS_OEM_ID:
                print("Invalid partition specified.")
                sys.exit(-1)
        else:
            self.part_offset = unpack("I", self.fh.read(0x1CA + ((partition - 1) * 0x10))[-4:])[0] * 512
            self.fh.seek(self.part_offset)
            if unpack(">Q", self.fh.read(0xB)[3:])[0] != NTFS_OEM_ID:
                print("Invalid partition specified.")
                sys.exit(-1)
        self.fh.seek(self.part_offset)
        """
        Grab FS data from the MBR
        """
        sb = bytearray(512)
        self.fh.readinto(sb)
        self.ssize = from_bytes(sb[0x0B:0x0D])
        self.csize = sb[0x0D] * self.ssize
        self.num_sectors = from_bytes(sb[0x28:0x30])
        self.num_bytes = self.num_sectors * self.ssize
        self.num_clusters = int(math.ceil(self.num_bytes / self.csize))
        self.mft_offset = from_bytes(sb[0x30:0x38]) * self.csize
        self.mft_mir_offset = from_bytes(sb[0x38:0x40]) * self.csize
        self.entry_size = sb[0x40]
        #self.serial_num = hex(from_bytes(sb[0x48:0x50]))

    def get_cluster_size(self):
        return self.csize

    def get_num_clusters(self):
        return self.num_clusters

    def setup_mft_data(self):
        """
        The $MFT file (MFT entry 0) stores information about all allocated MFT entries in its data section. This information is used
        to bootstrap the parser. While slightly more complex than just linearly reading each file entry, this method is able to handle
        the case where the MFT is fragmented and or an entry falls on a bad cluster.
        """
        self.fh.seek(self.mft_offset + self.part_offset, os.SEEK_SET)
        buf = bytearray(MFT_ENTRY_SIZE)
        self.fh.readinto(buf)
        buf = self.entry_fixup(buf)
        buf = buf[buf.find(DATA_SIG)::]
        data_len = from_bytes(buf[4:8])
        run_offset = from_bytes(buf[32:34])
        data = buf[run_offset:run_offset + data_len]
        self.mft_data = array.array("I")
        run_offset, prev_run_offset = 0, 0
        while True:
            rh = data.pop(0)
            run_offset_bytes = (rh & 0xF0) >> 4
            data_run_bytes = (rh & 0x0F)
            if not (run_offset_bytes & data_run_bytes):
                break
            data_run_len, run_offset = 0, 0
            #data_run_len = reduce(lambda x,y: x | (data.pop(0) << (y * 8)), range(data_run_bytes), 0)
            for i in range(data_run_bytes):
                data_run_len |= (data.pop(0) << (i * 8))
            #run_offset = reduce(lambda x,y: x | (data.pop(0) << (y * 8)), range(run_offset_bytes), 0)
            for i in range(run_offset_bytes):
                run_offset |= (data.pop(0) << (i * 8))
            run_offset = prev_run_offset + to_signed(run_offset, run_offset_bytes)
            prev_run_offset = run_offset
            self.mft_data.extend(range(run_offset, run_offset + data_run_len))
            if to_bytes(data[0], 1) == DATA_RUN_END:
                break

    def entry_fixup(self, buf):
        fixoff = from_bytes(buf[4:6]) + 2
        fixlen = from_bytes(buf[6:8]) + 1
        end = self.ssize - 2
        # For each sector in this entry, replace the fixup values with the original ones.
        for i in range(0, fixlen, 2):
            buf[end] = buf[fixoff + i]
            buf[end + 1] = buf[fixoff + i + 1]
            end += self.ssize
        return buf

    def create_SecurityDescriptorTable(self):
        pass

    def parse_mft_entry(self, inum=0):
        """
        The main method/function of the parser. It accepts a 'start' entry if only a single MFT entry's data is desired (in which case the 'end' parameter is set to the same
        value as 'start'). The optional parameters 'full_parse', 'quickstat' and 'cleanup' are used to somewhat fine-tune the parser so that no more parsing/processing occurs
        than necessary. The 'full_parse' option determines whether to completely parse idx root/entries (if entry is a directory) as well as attribute list information (if present)
        of an entry. The 'quickstat' option determines whether to parse the data run information for an entry. The 'cleanup' option determines whether to force the release of file
        entry objects from memory, as Python seems to be a little too lax on its garbage collection mechanisms. This is generally a good idea, as it cuts the memory usage
        of a full-parsing down significantly without adding too much overhead.
        """
        pos = [0.0, 0.25, 0.50, 0.75]
        try:
            idx, vcn = math.modf((inum * MFT_ENTRY_SIZE) / self.csize)
            idx = pos.index(idx)
            if int(vcn) >= len(self.mft_data):
                return
            lcn = self.mft_data[int(vcn)]
            address = (lcn * self.csize) + (idx * MFT_ENTRY_SIZE) + self.part_offset
            self.fh.seek(address, os.SEEK_SET)
            buf = bytearray(MFT_ENTRY_SIZE)
            self.fh.readinto(buf)
            if buf[0:4] == MFT_ENTRY_SIG:
                """ Beginning of MFT Entry """
                buf = self.entry_fixup(buf)
                entry = MFT_ENTRY()
                entry.header = self.parse_record_header(buf)
                entry.alloc_status = entry.header.flags & ALLOCATED
                entry.inum = entry.header.inum
                buf = buf[MFT_HEADER_LEN:]
                if entry.header.base != 0:
                # Part of a multi-entry data attribute, not a unique File Entry.
                # It will eventually be included in an Attribute List attribute
                    return entry
                while 1:
                    # Trudge through the entry one attribute at a time using their
                    # attribute id's (SIG) and entry lengths to identify attributes.
                    # All entries SHOULD begin with a standard header and end with
                    # the END_OF_ENTRY signature.
                    current_attr_sig = buf[0:4]
                    if current_attr_sig == STANDARD_INFO_SIG:
                        entry.attrs.append(self.parse_std_info(buf))
                        buf = buf[from_bytes(buf[4:8]):]

                    elif current_attr_sig == ATTR_LIST_SIG:
                        attr_entries = self.parse_attr_list(buf)
                        buf = buf[from_bytes(buf[4:8]):]
                        self.parse_attr_list_entries(inum, attr_entries, entry, buf)

                    elif current_attr_sig == FILENAME_SIG:
                        fname = self.parse_filename(buf)
                        buf = buf[from_bytes(buf[4:8]):]
                        if fname.nspace == 2:
                            continue
                        else:
                            entry.attrs.append(fname)

                    elif current_attr_sig == OBJECT_ID_SIG:
                        buf = buf[from_bytes(buf[4:8]):]
                        #self.parse_object_id()

                    elif current_attr_sig == SECURITY_DESC_SIG:
                        buf = buf[from_bytes(buf[4:8]):]
                        #self.parse_sec_desc(self.entry_offset)

                    elif current_attr_sig == VOLUME_NAME_SIG:
                        buf = buf[from_bytes(buf[4:8]):]
                        #self.parse_volume_name(self.entry_offset)

                    elif current_attr_sig == VOLUME_INFO_SIG:
                        buf = buf[from_bytes(buf[4:8]):]
                        #self.parse_volume_info(self.entry_offset)

                    elif current_attr_sig == BITMAP_SIG:
                        buf = buf[from_bytes(buf[4:8]):]

                    elif current_attr_sig == DATA_SIG:
                        if entry.alloc_status != UNALLOCATED:
                            entry.attrs.append(self.parse_data_attr(buf))
                        buf = buf[from_bytes(buf[4:8]):]

                    elif current_attr_sig == INDEX_ROOT_SIG:
                        buf = buf[from_bytes(buf[4:8]):]
                        """
                        if not self.parse_index_records or self.alloc_status == UNALLOCATED:
                            self.entry_offset += attr_len
                        else:
                            self.idx_root = self.parse_idx_root(self.entry_offset)
                        """

                    elif current_attr_sig == INDEX_ALLOC_SIG:
                        buf = buf[from_bytes(buf[4:8]):]
                        """
                        if not self.parse_index_records or self.alloc_status == UNALLOCATED:
                            self.entry_offset += attr_len
                        else:
                            self.idx_alloc = self.parse_idx_alloc(self.entry_offset)
                        """

                    elif current_attr_sig == LOG_UTIL_STREAM_SIG:
                        buf = buf[from_bytes(buf[4:8]):]

                    elif current_attr_sig == END_OF_ENTRY_SIG:
                        break
                    else:
                        # Where the hell are we? Just go to the next entry...
                        break
                """
                if self.entry_name != None and 'DIRECTORY' in self.flags:
                    parent = self.parent
                    entry_name = self.entry_name
                    while parent in directories and parent != 5:
                        parent_name, parent = directories[parent]
                        entry_name = parent_name + '/' + entry_name
                    directories[current] = (entry_name, parent)
                # We're not interested in MFT specific files nor deleted ones...

                if self.entry_name != None and self.entry_name[0] != '$' and self.alloc_status != UNALLOCATED and 'DIRECTORY' not in self.flags:
                    if self.real_size == 0:
                        size = self.data_size
                    else:
                        size = self.real_size
                    self.entries.append([self.entry_name, self.entry_num, self.path, self.parent, self.ctime, self.mtime, self.atime, size, self.clusters, self.res_data])

                if self.alloc_status != UNALLOCATED and self.name != None and self.name[0] != '$':
                    self.entries.append([self.name, self.inum, self.fileref, self.ctime, self.mtime, self.atime, self.rsize, self.data])
                """
                return entry
        except KeyboardInterrupt:
            print("User aborted")
            return
        """
        for entry in self.entries:
            parent =self.entry[3]
           self.entry[2] = directories[parent][0]
        """
        self.fh.close()
        #import cPickle
        #fh = open('filedump', 'wb')
        #pickle.dump(self.entries, fh)
        #return self.entries
        #gc.enable()


    def parse_record_header(self, buf):
        """ Parse the Standard MFT Entry header. All entries should begin with this header. SHOULD.. """
        # First things first, we need to deal with the fixup values. Grab the saved values from the fixup
        # array and place them where they belong, namely the last 2 bytes of each sector.
        header = ENTRY_HEADER()
        header.lsn = from_bytes(buf[8:16])
        header.seq_num = from_bytes(buf[16:18])
        header.lnk_cnt = from_bytes(buf[18:20])
        header.attr_off = from_bytes(buf[20:22])
        header.flags = from_bytes(buf[22:24])
        header.rsize = from_bytes(buf[24:28])
        header.asize = from_bytes(buf[28:32])
        header.base = from_bytes(buf[32:38])
        header.nextid = from_bytes(buf[40:42])
        header.inum = from_bytes(buf[44:48])
        return header

    def parse_resident_attribute(self, buf, attr_len):
        pass

    def parse_nonresident_attribute(self, buf, attr_len):
        pass

    def parse_attr_list(self, buf):
        """Parse the Attribute List attribute of an entry. Entries only have an attribute list if a single entry is too small
           to hold all the metadata of the entry's attributes."""
        attr_list_len = from_bytes(buf[4:8])
        nonresident = buf[8]
        attr_entries = []
        if nonresident == 0:
            buf = buf[24:24 + attr_list_len]
            attr_entries.append(self.parse_attr_list_headers(buf))
        else:
            vcn = from_bytes(buf[16:24]) & 0xFFFFFFFFFFFF
            offset = from_bytes(buf[32:34])
            asize = from_bytes(buf[40:48])
            run = buf[offset:offset + asize]
            handle = open(self.fh.name, 'rb')
            prev_offset = 0
            while True:
                rh = run.pop(0)
                offset_bytes = (rh & 0xF0) >> 4
                run_bytes = (rh & 0x0F)
                if not offset_bytes & run_bytes:
                    break
                run_len, offset = 0, 0
                for i in range(run_bytes):
                    run_len |= (run.pop(0) << (i * 8))
                for i in range(offset_bytes):
                    offset |= (run.pop(0) << (i * 8))
                offset = prev_offset + to_signed(offset, offset_bytes)
                prev_offset = offset
                for i in range(run_len):
                    lcn = (offset + i + vcn)
                    handle.seek((lcn * self.csize) + self.part_offset, os.SEEK_SET)
                    buf = bytearray(self.csize)
                    handle.readinto(buf)
                    attr_entries.append(self.parse_attr_list_headers(buf))
                if to_bytes(run[0], 1) == DATA_RUN_END:
                    break
            handle.close()
        return attr_entries

    def parse_attr_list_headers(self, buf):
        while len(buf) > 26:
            if from_bytes(buf[0:4]) == 0:
                break
            attr_entry = ATTR_LIST_ENTRY()
            attr_entry.atype = from_bytes(buf[0:4])
            attr_entry.attrlen = from_bytes(buf[4:6])
            namelen = buf[6]
            nameoff = buf[7]
            attr_entry.vcn = from_bytes(buf[8:16]) & 0xFFFFFFFFFFFF
            attr_entry.ref = from_bytes(buf[16:24]) & 0xFFFFFFFFFFFF
            attr_entry.attrid =  buf[24]
            name = buf[nameoff:nameoff + (2 * namelen)].replace(b'\x00', b'')
            attr_entry.name = ''.join([chr(x) for x in name])
            attr_entries.append(attr_entry)
            buf = buf[attrlen:]
        return attr_entries


    def parse_attr_list_entries(self, num, attr_entries, entry, buf):
        orig_img_offset = self.fh.tell()
        orig_buf = buf
        pos = [0.0, 0.25, 0.50, 0.75]
        refs = []
        for attr in attr_entries:
            if attr.ref not in refs:
                refs.append(attr.ref)
        for ref in refs:
            if ref != num:
                idx, vcn = math.modf((attr.ref * MFT_ENTRY_SIZE) / self.csize)
                idx = pos.index(idx)
                lcn = self.mft_data[int(vcn)]
                address = (lcn * self.csize) + (idx * MFT_ENTRY_SIZE) + self.part_offset
                self.fh.seek(address, os.SEEK_SET)
                buf = bytearray(MFT_ENTRY_SIZE)
                self.fh.readinto(buf)
                fixoff = from_bytes(buf[4:6]) + 2
                fixlen = from_bytes(buf[6:8]) + 1
                end = self.ssize - 2
                # For each sector in this entry, replace the fixup values with the original ones.
                for i in range(0, fixlen, 2):
                    buf[end] = buf[fixoff + i]
                    buf[end + 1] = buf[fixoff + i + 1]
                    end += self.ssize
                header = self.parse_record_header(buf)
                buf = buf[MFT_HEADER_LEN:]
                while 1:
                    if buf[0:4] == FILENAME_SIG:
                        fname = self.parse_filename(buf)
                        buf = buf[from_bytes(buf[4:8]):]
                        if fname.nspace == 2:
                            continue
                        else:
                            entry.attrs.append(fname)
                    elif buf[0:4] == DATA_SIG:
                        entry.attrs.append(self.parse_data_attr(buf))
                        buf = buf[from_bytes(buf[4:8]):]
                    elif buf[0:4] == END_OF_ENTRY_SIG:
                        break
                    else:
                        buf = buf[from_bytes(buf[4:8]):]
                self.fh.seek(orig_img_offset, os.SEEK_SET)
                buf = orig_buf
            else:
                while 1:
                    if buf[0:4] == FILENAME_SIG:
                        fname = self.parse_filename(buf)
                        buf = buf[from_bytes(buf[4:8]):]
                        if fname.nspace == 2:
                            continue
                        else:
                            entry.attrs.append(fname)
                    elif buf[0:4] == DATA_SIG:
                        entry.attrs.append(self.parse_data_attr(buf))
                        buf = buf[from_bytes(buf[4:8]):]
                    elif buf[0:4] == END_OF_ENTRY_SIG:
                        break
                    else:
                        buf = buf[from_bytes(buf[4:8]):]
        return

    '''
    def parse_attr_def(self, offset):
        offset += 4
        attr_name = self.entry[offset:offset+128]
        type_id = struct_i.unpack(self.entry[offset+128:offset+132])[0]
        display_rule = struct_i.unpack(self.entry[offset+132:offset+136])[0]
        collation_rule = struct_i.unpack(self.entry[offset+136:offset+140])[0]
        flags = struct_i.unpack(self.entry[offset+140:offset+144])[0]
        min_size = struct_q.unpack(self.entry[offset+144:offset+152])[0]
        max_size = struct_q.unpack(self.entry[offset+152:offset+160])[0]

    '''

    def parse_std_info(self, buf):
        std_info = STANDARD_INFO()
        std_info.ctime = from_bytes(buf[24:32])
        std_info.atime = from_bytes(buf[32:40])
        std_info.mtime = from_bytes(buf[40:48])
        std_info.rtime = from_bytes(buf[48:56])
        std_info.flags = [key for key in ATTRIBUTES if from_bytes(buf[56:60]) & ATTRIBUTES[key]]
        std_info.usn = from_bytes(buf[64:72])
        return std_info


    def parse_filename(self, buf):
        fname = FILENAME()
        fname.ref = from_bytes(buf[24:30])
        fname.ctime = from_bytes(buf[32:40])
        fname.atime = from_bytes(buf[40:48])
        fname.mtime = from_bytes(buf[48:56])
        fname.rtime = from_bytes(buf[56:64])
        fname.asize = from_bytes(buf[64:72])
        fname.rsize = from_bytes(buf[72:80])
        fname.flags = [key for key in ATTRIBUTES if from_bytes(buf[80:84]) & ATTRIBUTES[key]]
        fname.nspace = buf[89]
        name = buf[90: 90 + (2 * buf[88])].replace(b'\x00', b'')
        fname.name = ''.join([chr(x) for x in name])
        return fname

    def parse_object_id(self):
        length = unpack_from("<I", self.entry, 4)[0]
        object_id = b2a_hex(self.entry[length-24:23:-1])
        obj_id = object_id[0:8]

        object_id = '-'.join([object_id[0:8], object_id[8:12], object_id[12:16], object_id[16:20], object_id[20:]])
        self.entry = self.entry[40:]
        return OBJECT_ID(object_id[0:8], object_id[8:12], object_id[12:16], object_id[16:20], )
        """
        #self.entry_offset += 40
        return None

    def parse_volume_name(self, offset):
        self.entry_offset += struct_i.unpack(self.entry[offset + 4:offset + 8])[0]
        return None

    def parse_volume_info(self, offset):
        self.entry_offset += struct_i.unpack(self.entry[offset + 4:offset + 8])[0]
        return None

    """
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
        orig_img_offset = self.fh.tell()
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
            rh = data.pop(0)
            run_offset_bytes = (rh & 0xF0) >> 4
            data_run_bytes = (rh & 0x0F)
            if 0 in (run_offset_bytes, data_run_bytes):
                break
            data_run_len = 0
            run_offset = 0
            #data_run_len = reduce(lambda x,y: x | (data.pop(0) << (y * 8)), range(data_run_bytes), 0)
            for i in range(data_run_bytes):
                data_run_len |= (data.pop(0) << (i * 8))
            #run_offset = reduce(lambda x,y: x | (data.pop(0) << (y * 8)), range(run_offset_bytes), 0)
            for i in range(run_offset_bytes):
                run_offset |= (data.pop(0) << (i * 8))
            run_offset = prev_run_offset + to_signed(run_offset, run_offset_bytes)
            prev_run_offset = run_offset
            clusters.extend(range(run_offset, run_offset + data_run_len))
            if to_bytes(data[0], 1) == DATA_RUN_END:
                break
        self.entry_offset += attr_len
        self.fh.seek(orig_img_offset)
        return INDEX_ALLOC(attr_name, attr_flags, attr_id, start_vcn, end_vcn, run_len, idx_blocks, clusters)

    def parse_index_block(self, lcn):
        self.fh.seek((lcn * self.csize) + self.part_offset, os.SEEK_SET)
        index_block = self.fh.read(self.csize)
        fixup_offset = struct_h.unpack(index_block[4:6])[0] + 2
        fixup_len = struct_h.unpack(index_block[6:8])[0] + 1
        log_seq = struct_q.unpack(index_block[8:16])[0]
        index_block_vcn = struct_q.unpack(index_block[16:24])[0] & 0xFFFFFFFF
        sec_end = self.ssize - 2
        index_block = list(index_block)
        for i in range(0, fixup_len, 2):
            index_block[sec_end:sec_end + 1] = index_block[fixup_offset + i:fixup_offset + i + 1]
            sec_end += self.ssize
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
            if self.get_mactimes:
                try:
                    entry_ctime = time.ctime((struct_q.unpack(index_buffer[offset + 24:offset + 32])[0] - NTFS_EPOCH) / 10 ** (7))
                    entry_mtime = time.ctime((struct_q.unpack(index_buffer[offset + 40:offset + 48])[0] - NTFS_EPOCH) / 10 ** (7))
                    entry_atime = time.ctime((struct_q.unpack(index_buffer[offset + 48:offset + 56])[0] - NTFS_EPOCH) / 10 ** (7))
                except:
                    pass
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

    def parse_data_attr(self, buf):
        data_attr = DATA_ATTR()
        data_attr.nonresident = buf[8]
        nlength = buf[9]
        noffset = from_bytes(buf[10:12])
        data_attr.vcn = 0
        data_attr.lvcn = 0
        if nlength != 0:
            name = buf[noffset:noffset + (2 * nlength)].replace(b'\x00', b'')
            name = ''.join([chr(x) for x in name])
        else:
            name = None
        data_attr.name = name
        flags = [key for key in ATTRIBUTES if from_bytes(buf[12:14]) & ATTRIBUTES[key]]
        data_attr.attrid = from_bytes(buf[14:16])
        if data_attr.nonresident:
            data_attr.vcn = from_bytes(buf[16:24]) & 0xFFFFFFFFFFFF
            data_attr.lvcn = from_bytes(buf[24:32]) & 0xFFFFFFFFFFFF
            offset = from_bytes(buf[32:34])
            asize = from_bytes(buf[40:48])
            data_attr.rsize = from_bytes(buf[48:56])
            run = buf[offset:offset + asize]
            prev_offset = 0
            data = []
            while True:
                rh = run.pop(0)
                offset_bytes = (rh & 0xF0) >> 4
                run_bytes = (rh & 0x0F)
                if 0 in (offset_bytes, run_bytes):
                    break
                run_len = 0
                offset = 0
                #data_run_len = reduce(lambda x,y: x | (data.pop(0) << (y * 8)), range(data_run_bytes), 0)
                for i in range(run_bytes):
                    run_len |= (run.pop(0) << (i * 8))
                #run_offset = reduce(lambda x,y: x | (data.pop(0) << (y * 8)), range(run_offset_bytes), 0)
                for i in range(offset_bytes):
                    offset |= (run.pop(0) << (i * 8))
                offset = prev_offset + to_signed(offset, offset_bytes)
                prev_offset = offset
                data.append((offset, run_len))
                if to_bytes(run[0], 1) == DATA_RUN_END:
                    break
            data_attr.data = data
        else:
            data_attr.rsize = from_bytes(buf[12:16])
            offset = from_bytes(buf[20:22])
            data_attr.data = buf[offset:offset+data_attr.rsize]
        return data_attr

    def parse_bitmap_attr(self, offset):
        self.entry_offset += struct_i.unpack(self.entry[offset + 4:offset + 8])[0]
        return None

    def parse_sec_desc(self, offset):
        self.entry_offset += struct_i.unpack(self.entry[offset + 4:offset + 8])[0]
        return None

def main():
    mft = MFTParser(r'\\.\C:')
    mft.setup_mft_data()
    p = mft.parse_mft_entry(3207)
    #self.setup_mft_data()
    return p
if __name__ == "__main__":
    main()