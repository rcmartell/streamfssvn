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
    def __init__(self, name=None, parent=None, real_size=None, data_size=None, clusters=None, res_data=None):
        self.name = name
        self.parent = parent
        self.real_size = real_size
        self.data_size = data_size
        self.clusters = clusters
        self.res_data = res_data

class MFT_STANDARD_HEADER():
    """Standard MFT Entry header. All entries should start with one...Should..."""
    def __init__(self,lsn=None, seq_num=None, lnk_cnt=None,flags=None, entry_num=None, mft_base=None):
        self.lsn = lsn
        self.seq_num = seq_num
        self.lnk_cnt = lnk_cnt
        self.flags = flags
        self.entry_num = entry_num
        self.mft_base = mft_base

class STANDARD_INFO():
    """Standard MAC time info and flags"""
    def __init__(self, ctime=None, mtime=None, atime=None, flags=None):
        self.ctime = ctime
        self.mtime = mtime
        self.atime = atime
        self.flags = flags

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

class IDX_ROOT():
    def __init__(self, attr_type=None, idx_entries=None):
        self.attr_type = attr_type
        self.idx_entries = idx_entries

class IDX_ALLOC():
    def __init__(self, idx_entries=None):
        self.idx_entries = idx_entries

class IDX_ENTRY():
    def __init__(self, entry_len=None, content_len=None, flags=None, content=None, vcn=None):
        self.entry_len = entry_len
        self.content_len = content_len
        self.flags = flags
        self.content = content
        self.vcn = vcn

class SECURE_FILE():
    def __init__(self, sii=None, sdh=None, sds=None):
        self.sii = sii
        self.sdh = sdh
        self.sds = sds

class ATTR_LIST():
    def __init__(self, attr_type=None, entry_len=None, entry_name_len=None, start_vcn=None, mft_entry=None, attr_id=None):
        self.attr_type = attr_type
        self.entry_len = entry_len
        self.entry_name_len = entry_name_len
        self.start_vcn = start_vcn
        self.mft_entry = mft_entry
        self.attr_id = attr_id

class DATA():
    def __init__(self, attr_type=None, nonresident=None, flags=None, attr_id=None, start_vcn=None, end_vcn=None,
                 alloc_size=None, real_size=None, clusters=None, file_fragmented=False, res_data=None, name=None):
        self.attr_type = attr_type
        self.nonresident = nonresident
        self.flags = flags
        self.attr_id = attr_id
        self.start_vcn = start_vcn
        self.end_vcn = end_vcn
        self.alloc_size = alloc_size
        self.real_size = real_size
        self.clusters = clusters
        self.file_fragmented = file_fragmented
        self.res_data = res_data
        self.name = name

class PDATA():
    def __init__(self, data_size=None, clusters=None, res_data=None):
        self.data_size = data_size
        self.clusters = clusters
        self.res_data = res_data

class BITMAP():
    def __init__(self, bmap=None):
        self.bmap = bmap
