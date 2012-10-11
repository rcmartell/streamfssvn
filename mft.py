class MFT_ENTRY():
    """Object representing a standard MFT Entry"""
    def __init__(self, entry_num=None, std_info=None, attr_list=None, filename=None, object_id=None,
                 sec_file=None, idx_root=None, idx_alloc=None, data=None, bitmap=None):
        self.entry_num = entry_num
        self.std_info = std_info
        self.attr_list = attr_list
        self.filename = filename
        self.sec_file = sec_file
        self.object_id = object_id
        self.idx_root = idx_root
        self.idx_alloc = idx_alloc
        self.data = data
        self.bitmap = bitmap

class FILE_RECORD(object):
    def __init__(self, name=None, entry_num=0, parent=None, ctime=None, mtime=None, atime=None, size=None, clusters=None, res_data=None):
        self.name = name
        self.entry_num = entry_num
        self.parent = parent
        self.ctime = ctime
        self.mtime = mtime
        self.atime = atime
        self.size = size
        self.clusters = clusters
        self.res_data = res_data

class MFT_STANDARD_HEADER():
    """Standard MFT Entry header. All entries should start with one...Should..."""
    def __init__(self, lsn=None, seq_num=None, lnk_cnt=None, flags=None, entry_num=None, mft_base=None):
        self.lsn = lsn
        self.seq_num = seq_num
        self.lnk_cnt = lnk_cnt
        self.flags = flags
        self.entry_num = entry_num
        self.mft_base = mft_base

class STANDARD_INFO():
    """Standard MAC time info and flags"""
    def __init__(self, ctime=None, mtime=None, atime=None, flags=None, sid=None):
        self.ctime = ctime
        self.mtime = mtime
        self.atime = atime
        self.flags = flags
        self.sid = sid

class FILENAME():
    """Standard filename entry info"""
    def __init__(self, parent=None, ctime=None, mtime=None, atime=None,
                 alloc_size=None, real_size=None, flags=None, name_len=None, name=None, seq_num=None, namespace=None):
        self.parent = parent
        self.ctime = ctime
        self.mtime = mtime
        self.atime = atime
        self.alloc_size = alloc_size
        self.real_size = real_size
        self.flags = flags
        self.name_len = name_len
        self.name = name
        self.seq_num = seq_num
        self.namespace = namespace

class OBJECT_ID():
    def __init__(self, object_id=None):
        self.object_id = object_id

class INDEX_ROOT():
    def __init__(self, attr_name=None, attr_flags=None, attr_id=None, idx_size=None, header_flags=None, idx_entries=[]):
        self.attr_name = attr_name
        self.attr_flags = attr_flags
        self.attr_id = attr_id
        self.idx_size = idx_size
        self.header_flags = header_flags
        self.idx_entries = idx_entries

class INDEX_ALLOC():
    def __init__(self, attr_name=None, attr_flags=None, attr_id=None, start_vcn=None, end_vcn=None, data_size=None, idx_blocks=[], clusters=None):
        self.attr_name = attr_name
        self.attr_flags = attr_flags
        self.attr_id = attr_id
        self.start_vcn = start_vcn
        self.end_vcn = end_vcn
        self.data_size = data_size
        self.idx_blocks = idx_blocks
        self.clusters = clusters
        

class INDEX_BLOCK():
    def __init__(self, log_seq = None, idx_block_vcn = None, idx_size = None, alloc_size = None, header_flags = None, idx_entries=[]):
        self.log_seq = log_seq
        self.idx_block_vcn = idx_block_vcn
        self.idx_size = idx_size
        self.alloc_size = alloc_size
        self.header_flags = header_flags
        self.idx_entries = idx_entries

class INDEX_ENTRY():
    def __init__(self, mft_ref=None, flags=None, parent_ref=None, ctime=None, mtime=None, atime=None, alloc_size=None, real_size=None, file_flags=None, name=None):
        self.mft_ref = mft_ref
        self.flags = flags
        self.parent_ref = parent_ref
        self.ctime = ctime
        self.mtime = mtime
        self.atime = atime
        self.alloc_size = alloc_size
        self.real_size = real_size
        self.file_flags = file_flags
        self.name = name

class SECURE_FILE():
    def __init__(self, sii=None, sdh=None, sds=None):
        self.sii = sii
        self.sdh = sdh
        self.sds = sds
        
class ATTR_LIST():
    def __init__(self, nonresident=None, size=None, init_size=None, attr_entries=[], clusters=None):
        self.nonresident = nonresident
        self.size = size
        self.init_size = init_size
        self.attr_entries = attr_entries
        self.clusters = clusters

class ATTR_LIST_ENTRY():
    def __init__(self, attr_type=None, attr_len=None, name_len=None, start_vcn=None, mft_ref=None, attr_id=None, attr_name=None):
        self.attr_type = attr_type        
        self.attr_len = attr_len
        self.name_len = name_len
        self.start_vcn = start_vcn
        self.mft_ref = mft_ref
        self.attr_id = attr_id
        self.attr_name = attr_name

class DATA_ATTR():
    def __init__(self, nonresident=None, flags=None, attr_id=None, start_vcn=None, end_vcn=None,
                 alloc_size=None, data_size=None, clusters=None, file_fragmented=False, res_data=None, attr_name=None):
        self.nonresident = nonresident
        self.flags = flags
        self.attr_id = attr_id
        self.start_vcn = start_vcn
        self.end_vcn = end_vcn
        self.alloc_size = alloc_size
        self.data_size = data_size
        self.clusters = clusters
        self.file_fragmented = file_fragmented
        self.res_data = res_data
        self.attr_name = attr_name

class BITMAP():
    def __init__(self, bmap=None):
        self.bmap = bmap

class SECURITY_DESCRIPTOR():
    def __init__(self, sacl=None, dacl=None, user_sid=None, group_sid=None):
        self.sacl = sacl
        self.dacl = dacl
        self.user_sid = user_sid
        self.group_sid = group_sid
        
class ACE():
    def __init__(self, acetype=None, flags=None, size=None, access_mask=None, sid=None):
        self.acetype = acetype
        self.flags = flags
        self.size = size
        self.access_mask = access_mask
        self.sid = sid
